"""
/payments/dodo/* DodoPayments 웹 결제 라우터
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from dodopayments import DodoPayments
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db, _verify_firebase_token, _get_or_create_user
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments/dodo", tags=["dodopayments"])


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _dodo_product_to_plan(product_id: str) -> str | None:
    """product_id → plan 매핑 (base plan + billing_interval)."""
    _map = {
        settings.dodo_product_pro: ("pro", "monthly"),
        settings.dodo_product_proplus: ("pro_plus", "monthly"),
        settings.dodo_product_pro_annual: ("pro", "annual"),
        settings.dodo_product_proplus_annual: ("pro_plus", "annual"),
        settings.dodo_product_pro_lifetime: ("pro", "lifetime"),
        settings.dodo_product_proplus_lifetime: ("pro_plus", "lifetime"),
    }
    result = _map.get(product_id)
    if result:
        return result[0]  # base plan for backward compat
    return None


def _dodo_product_to_billing_interval(product_id: str) -> str:
    """product_id → billing_interval."""
    _map = {
        settings.dodo_product_pro: "monthly",
        settings.dodo_product_proplus: "monthly",
        settings.dodo_product_pro_annual: "annual",
        settings.dodo_product_proplus_annual: "annual",
        settings.dodo_product_pro_lifetime: "lifetime",
        settings.dodo_product_proplus_lifetime: "lifetime",
    }
    return _map.get(product_id, "monthly")


def _plan_to_dodo_product(plan: str, billing_interval: str = "monthly") -> str | None:
    """plan + billing_interval → product_id 매핑."""
    if billing_interval == "annual":
        if plan == "pro":
            return settings.dodo_product_pro_annual
        if plan == "pro_plus":
            return settings.dodo_product_proplus_annual
    elif billing_interval == "lifetime":
        if plan == "pro":
            return settings.dodo_product_pro_lifetime
        if plan == "pro_plus":
            return settings.dodo_product_proplus_lifetime
    else:  # monthly
        if plan == "pro":
            return settings.dodo_product_pro
        if plan == "pro_plus":
            return settings.dodo_product_proplus
    return None


async def _find_sub_by_dodo_id(dodo_subscription_id: str, db: AsyncSession) -> Subscription | None:
    """dodo_subscription_id로 구독 조회."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.dodo_subscription_id == dodo_subscription_id,
        ).limit(1)
    )
    return result.scalar_one_or_none()


def _get_dodo_client() -> DodoPayments:
    return DodoPayments(
        bearer_token=settings.dodo_api_key,
        environment=settings.dodo_environment,
    )


# ── 스키마 ────────────────────────────────────────────────────────────────────

class CheckoutBody(BaseModel):
    plan: str  # "pro" | "pro_plus"
    billing_interval: str = "monthly"  # "monthly" | "annual" | "lifetime"


class TossCheckoutBody(BaseModel):
    plan: str  # "pro" | "pro_plus"
    token: str  # Firebase ID Token (Toss WebView에서는 Authorization 헤더 대신 body로 전달)
    billing_interval: str = "monthly"


# ── Checkout 생성 ─────────────────────────────────────────────────────────────

@router.post("/create-checkout")
async def create_checkout(
    body: CheckoutBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """DodoPayments Checkout URL 생성."""
    if body.plan not in ("pro", "pro_plus"):
        raise HTTPException(422, detail="유효하지 않은 플랜입니다. pro 또는 pro_plus만 가능합니다.")
    if body.billing_interval not in ("monthly", "annual", "lifetime"):
        raise HTTPException(422, detail="유효하지 않은 결제 주기입니다.")

    product_id = _plan_to_dodo_product(body.plan, body.billing_interval)
    if not product_id:
        raise HTTPException(500, detail="DodoPayments 상품 ID가 설정되지 않았습니다.")

    if not settings.dodo_api_key:
        raise HTTPException(500, detail="DodoPayments API 키가 설정되지 않았습니다.")

    # 기존 활성 구독 처리 (업그레이드/중복 방지)
    # Trial 구독은 여기서 만료하지 않음 — subscription.active 웹훅에서 처리
    # (체크아웃 미완료 시 trial이 조기 만료되는 버그 방지)
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "grace_period"]),
        )
    )
    now = datetime.now(timezone.utc)
    for existing_sub in existing_result.scalars().all():
        if existing_sub.plan == body.plan and existing_sub.billing_interval == body.billing_interval:
            raise HTTPException(409, detail="이미 같은 플랜·결제 주기의 활성 구독이 있습니다.")
        else:
            existing_sub.status = "cancelled"
            existing_sub.cancelled_at = now
            existing_sub.updated_at = now
            logger.info(
                "기존 구독 취소: user=%s plan=%s/%s → 새 플랜 %s/%s 전환",
                current_user.id, existing_sub.plan, existing_sub.billing_interval, body.plan, body.billing_interval,
            )

    # 이메일이 없는 유저(토스 등) → 플레이스홀더 사용
    customer_email = current_user.email
    if not customer_email:
        customer_email = f"user_{current_user.id}@wewantpeace.live"

    # DodoPayments Checkout Session 생성
    client = _get_dodo_client()
    session = client.checkout_sessions.create(
        product_cart=[{"product_id": product_id, "quantity": 1}],
        customer={"email": customer_email, "name": current_user.display_name or "사용자"},
        return_url="https://www.wewantpeace.live/upgrade/success",
        metadata={"user_id": str(current_user.id), "plan": body.plan, "billing_interval": body.billing_interval},
    )

    logger.info(
        "DodoPayments checkout 생성: user=%s plan=%s billing=%s product=%s",
        current_user.id, body.plan, body.billing_interval, product_id,
    )

    return {
        "checkout_url": session.checkout_url,
        "plan": body.plan,
    }


# ── Toss WebView 전용: Form-urlencoded fetch (CORS preflight 우회) ────────────

@router.post("/create-checkout-simple")
async def create_checkout_simple(
    plan: str = Form(...),
    token: str = Form(...),
    billing_interval: str = Form("monthly"),
    db: AsyncSession = Depends(get_db),
):
    """
    Toss WebView 전용: application/x-www-form-urlencoded로 전송하면
    CORS 'Simple Request'가 되어 preflight(OPTIONS) 없이 바로 전송됨.
    JSON 응답으로 checkout_url 반환.
    """
    token_info = _verify_firebase_token(token)
    if not token_info or not token_info.get("uid"):
        raise HTTPException(401, detail="유효하지 않은 토큰입니다.")

    current_user = await _get_or_create_user(token_info["uid"], db, email=token_info.get("email"))

    if plan not in ("pro", "pro_plus"):
        raise HTTPException(422, detail="유효하지 않은 플랜입니다.")
    if billing_interval not in ("monthly", "annual", "lifetime"):
        billing_interval = "monthly"

    product_id = _plan_to_dodo_product(plan, billing_interval)
    if not product_id:
        raise HTTPException(500, detail="DodoPayments 상품 ID가 설정되지 않았습니다.")

    if not settings.dodo_api_key:
        raise HTTPException(500, detail="DodoPayments API 키가 설정되지 않았습니다.")

    # 기존 구독 처리 (Trial은 웹훅에서 만료 — 체크아웃 미완료 시 조기 만료 방지)
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "grace_period"]),
        )
    )
    now = datetime.now(timezone.utc)
    for existing_sub in existing_result.scalars().all():
        if existing_sub.plan == plan and existing_sub.billing_interval == billing_interval:
            raise HTTPException(409, detail="이미 같은 플랜·결제 주기의 활성 구독이 있습니다.")
        else:
            existing_sub.status = "cancelled"
            existing_sub.cancelled_at = now
            existing_sub.updated_at = now

    # 토스 유저는 이메일이 없을 수 있음 → 플레이스홀더 사용
    customer_email = current_user.email
    if not customer_email:
        customer_email = f"toss_{current_user.id}@wewantpeace.live"

    try:
        client = _get_dodo_client()
        session = client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer={"email": customer_email, "name": current_user.display_name or "토스 사용자"},
            return_url="https://www.wewantpeace.live/upgrade/success",
            metadata={"user_id": str(current_user.id), "plan": plan, "billing_interval": billing_interval},
        )
    except Exception as e:
        logger.error("DodoPayments create-checkout-simple 실패: user=%s error=%s", current_user.id, e)
        raise HTTPException(502, detail=f"결제 생성 실패: {str(e)[:200]}")

    logger.info("DodoPayments simple checkout: user=%s plan=%s billing=%s", current_user.id, plan, billing_interval)
    return {"checkout_url": session.checkout_url, "plan": plan}


# ── 웹훅 ─────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def dodo_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """DodoPayments 웹훅 수신 (Standard Webhooks 서명 검증, 인증 불필요)."""
    raw_body = await request.body()

    if not settings.dodo_webhook_key:
        logger.warning("DodoPayments webhook key 미설정 - 서명 검증 불가")
        raise HTTPException(403, detail="Webhook key not configured")

    # Standard Webhooks 서명 검증 + 이벤트 파싱
    try:
        client = _get_dodo_client()
        event = client.webhooks.unwrap(
            payload=raw_body.decode("utf-8"),
            headers=dict(request.headers),
            key=settings.dodo_webhook_key,
        )
    except Exception as e:
        logger.warning("DodoPayments 웹훅 서명 검증 실패: %s", e)
        raise HTTPException(403, detail="Invalid signature")

    event_type = event.type
    logger.info("DodoPayments 웹훅 수신: type=%s", event_type)

    # 구독 이벤트 처리
    if event_type == "subscription.active":
        await _handle_subscription_active(event.data, db)
    elif event_type == "subscription.renewed":
        await _handle_subscription_renewed(event.data, db)
    elif event_type == "subscription.cancelled":
        await _handle_subscription_cancelled(event.data, db)
    elif event_type == "subscription.expired":
        await _handle_subscription_expired(event.data, db)
    elif event_type in ("subscription.failed", "subscription.on_hold"):
        await _handle_subscription_retry(event.data, db)
    elif event_type == "payment.succeeded":
        await _handle_payment_succeeded(event.data, db)
    elif event_type == "payment.failed":
        logger.info("DodoPayments 결제 실패 이벤트: payment_id=%s", getattr(event.data, "payment_id", "?"))
    else:
        logger.info("DodoPayments 처리하지 않는 이벤트: %s", event_type)

    return {"status": "ok"}


# ── 이벤트 핸들러 ─────────────────────────────────────────────────────────────

async def _handle_subscription_active(data, db: AsyncSession) -> None:
    """subscription.active: 구독 생성/활성화, user.plan 업데이트."""
    dodo_sub_id = data.subscription_id
    product_id = data.product_id
    customer = data.customer
    metadata = data.metadata or {}
    user_id_str = metadata.get("user_id", "")

    plan = _dodo_product_to_plan(product_id)
    if not plan:
        logger.error("DodoPayments subscription.active: 알 수 없는 product_id=%s", product_id)
        return

    if not user_id_str:
        logger.error("DodoPayments subscription.active: user_id 누락 (metadata=%s)", metadata)
        return

    try:
        user_id = _uuid.UUID(user_id_str)
    except ValueError:
        logger.error("DodoPayments subscription.active: 유효하지 않은 user_id=%s", user_id_str)
        return

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error("DodoPayments subscription.active: 사용자를 찾을 수 없음 user_id=%s", user_id_str)
        return

    now = datetime.now(timezone.utc)
    next_billing = data.next_billing_date
    expires_at = data.expires_at or next_billing

    billing_interval = _dodo_product_to_billing_interval(product_id)

    # 기존 DodoPayments 구독이 있으면 업데이트
    existing = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if existing:
        existing.status = "active"
        existing.plan = plan
        existing.dodo_product_id = product_id
        existing.billing_interval = billing_interval
        existing.expires_at = expires_at
        existing.next_billing_at = next_billing
        existing.updated_at = now
    else:
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            platform="dodopayments",
            amount=data.recurring_pre_tax_amount,
            currency=str(data.currency),
            billing_interval=billing_interval,
            dodo_subscription_id=dodo_sub_id,
            dodo_customer_id=customer.customer_id if customer else None,
            dodo_product_id=product_id,
            auto_renewing=not data.cancel_at_next_billing_date if billing_interval != "lifetime" else False,
            started_at=now,
            expires_at=expires_at if billing_interval != "lifetime" else None,
            next_billing_at=next_billing if billing_interval != "lifetime" else None,
        )
        db.add(sub)

    # 기존 trial/active 구독 만료 처리 (체크아웃 시작이 아닌 결제 확정 시점에 정리)
    new_sub_id = existing.id if existing else sub.id
    old_subs_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trial", "grace_period"]),
            Subscription.id != new_sub_id,
        )
    )
    for old_sub in old_subs_result.scalars().all():
        old_sub.status = "expired" if old_sub.status == "trial" else "cancelled"
        old_sub.cancelled_at = now
        old_sub.updated_at = now
        logger.info(
            "DodoPayments 구독 활성화 → 기존 구독 정리: sub=%s status=%s→%s",
            old_sub.id, "trial" if old_sub.status == "expired" else "active", old_sub.status,
        )

    # admin 수동 설정된 유저는 웹훅으로 변경하지 않음
    if user.admin_plan_override:
        logger.info(
            "DodoPayments 구독 활성화 스킵 (admin_plan_override): user=%s plan=%s",
            user_id, plan,
        )
        await db.flush()
        return

    # user.plan 변경
    user.plan = plan
    await sync_area_activation(user_id, plan, db)
    await db.flush()

    logger.info(
        "DodoPayments 구독 활성화: user=%s plan=%s dodo_sub=%s",
        user_id, plan, dodo_sub_id,
    )


async def _handle_subscription_renewed(data, db: AsyncSession) -> None:
    """subscription.renewed: expires_at 갱신, PaymentHistory 기록."""
    dodo_sub_id = data.subscription_id
    sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if not sub:
        logger.warning("DodoPayments renewed: 구독을 찾을 수 없음 dodo_sub=%s", dodo_sub_id)
        return

    now = datetime.now(timezone.utc)
    next_billing = data.next_billing_date
    expires_at = data.expires_at or next_billing

    sub.status = "active"
    sub.expires_at = expires_at
    sub.next_billing_at = next_billing
    sub.updated_at = now

    # PaymentHistory 기록
    history = PaymentHistory(
        user_id=sub.user_id,
        subscription_id=sub.id,
        amount=data.recurring_pre_tax_amount,
        currency=str(data.currency),
        status="success",
        platform="dodopayments",
        pg_transaction_id=dodo_sub_id,
    )
    db.add(history)
    await db.flush()

    logger.info("DodoPayments 구독 갱신: dodo_sub=%s expires_at=%s", dodo_sub_id, expires_at)


async def _handle_subscription_cancelled(data, db: AsyncSession) -> None:
    """subscription.cancelled: status=cancelled, auto_renewing=False."""
    dodo_sub_id = data.subscription_id
    sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if not sub:
        logger.warning("DodoPayments cancelled: 구독을 찾을 수 없음 dodo_sub=%s", dodo_sub_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "cancelled"
    sub.cancelled_at = data.cancelled_at or now
    sub.auto_renewing = False
    if data.expires_at:
        sub.expires_at = data.expires_at
    sub.updated_at = now
    await db.flush()

    logger.info("DodoPayments 구독 취소: dodo_sub=%s expires_at=%s", dodo_sub_id, sub.expires_at)


async def _handle_subscription_expired(data, db: AsyncSession) -> None:
    """subscription.expired: user.plan=free, 구독 만료 처리."""
    dodo_sub_id = data.subscription_id
    sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if not sub:
        logger.warning("DodoPayments expired: 구독을 찾을 수 없음 dodo_sub=%s", dodo_sub_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "expired"
    sub.updated_at = now

    # 사용자 free 전환
    user_result = await db.execute(select(User).where(User.id == sub.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.plan = "free"
        await sync_area_activation(user.id, "free", db)

    await db.flush()

    logger.info("DodoPayments 구독 만료: dodo_sub=%s user=%s", dodo_sub_id, sub.user_id)


async def _handle_subscription_retry(data, db: AsyncSession) -> None:
    """subscription.failed / subscription.on_hold: status=billing_retry."""
    dodo_sub_id = data.subscription_id
    sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if not sub:
        logger.warning("DodoPayments retry: 구독을 찾을 수 없음 dodo_sub=%s", dodo_sub_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "billing_retry"
    sub.updated_at = now
    await db.flush()

    logger.info("DodoPayments 결제 재시도: dodo_sub=%s user=%s", dodo_sub_id, sub.user_id)


async def _handle_payment_succeeded(data, db: AsyncSession) -> None:
    """payment.succeeded: PaymentHistory 기록 + lifetime 일회성 결제 처리."""
    payment_id = data.payment_id
    dodo_sub_id = getattr(data, "subscription_id", None)

    # 구독 결제인 경우: PaymentHistory만 기록 (구독 활성화는 subscription.active에서 처리)
    if dodo_sub_id:
        sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
        if not sub:
            logger.warning("DodoPayments payment_succeeded: 구독을 찾을 수 없음 dodo_sub=%s", dodo_sub_id)
            return

        history = PaymentHistory(
            user_id=sub.user_id,
            subscription_id=sub.id,
            amount=data.total_amount,
            currency=str(data.currency),
            status="success",
            platform="dodopayments",
            pg_transaction_id=payment_id,
        )
        db.add(history)
        await db.flush()

        logger.info("DodoPayments 결제 성공 기록: payment_id=%s dodo_sub=%s", payment_id, dodo_sub_id)
        return

    # 일회성 결제 (lifetime): metadata에서 사용자 정보 추출하여 구독 생성
    product_id = getattr(data, "product_id", None)
    metadata = getattr(data, "metadata", None) or {}
    user_id_str = metadata.get("user_id", "")

    if not product_id:
        logger.info("DodoPayments 일회성 결제 성공 (product_id 없음): payment_id=%s", payment_id)
        return

    billing_interval = _dodo_product_to_billing_interval(product_id)
    plan = _dodo_product_to_plan(product_id)

    if billing_interval != "lifetime" or not plan:
        logger.info("DodoPayments 일회성 결제 성공 (non-lifetime): payment_id=%s product=%s", payment_id, product_id)
        return

    if not user_id_str:
        logger.error("DodoPayments lifetime 결제: user_id 누락 (metadata=%s, payment=%s)", metadata, payment_id)
        return

    try:
        user_id = _uuid.UUID(user_id_str)
    except ValueError:
        logger.error("DodoPayments lifetime 결제: 유효하지 않은 user_id=%s", user_id_str)
        return

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error("DodoPayments lifetime 결제: 사용자를 찾을 수 없음 user_id=%s", user_id_str)
        return

    now = datetime.now(timezone.utc)

    # 기존 활성 구독 모두 만료 처리
    old_subs_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trial", "grace_period"]),
        )
    )
    for old_sub in old_subs_result.scalars().all():
        old_sub.status = "expired" if old_sub.status == "trial" else "cancelled"
        old_sub.cancelled_at = now
        old_sub.updated_at = now

    # lifetime 구독 레코드 생성
    sub = Subscription(
        user_id=user_id,
        plan=plan,
        status="active",
        platform="dodopayments",
        amount=data.total_amount,
        currency=str(getattr(data, "currency", "USD")),
        billing_interval="lifetime",
        dodo_product_id=product_id,
        auto_renewing=False,
        started_at=now,
        expires_at=None,
        next_billing_at=None,
    )
    db.add(sub)

    # PaymentHistory 기록
    history = PaymentHistory(
        user_id=user_id,
        subscription_id=sub.id,
        amount=data.total_amount,
        currency=str(getattr(data, "currency", "USD")),
        status="success",
        platform="dodopayments",
        pg_transaction_id=payment_id,
    )
    db.add(history)

    # user.plan 업데이트
    if not user.admin_plan_override:
        user.plan = plan
        await sync_area_activation(user_id, plan, db)

    await db.flush()

    logger.info(
        "DodoPayments lifetime 결제 처리 완료: user=%s plan=%s payment=%s",
        user_id, plan, payment_id,
    )
