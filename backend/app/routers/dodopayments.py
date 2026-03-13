"""
/payments/dodo/* DodoPayments 웹 결제 라우터
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from dodopayments import DodoPayments
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments/dodo", tags=["dodopayments"])


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _dodo_product_to_plan(product_id: str) -> str | None:
    """product_id → plan 매핑."""
    if product_id == settings.dodo_product_pro:
        return "pro"
    if product_id == settings.dodo_product_proplus:
        return "pro_plus"
    return None


def _plan_to_dodo_product(plan: str) -> str | None:
    """plan → product_id 매핑."""
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

    product_id = _plan_to_dodo_product(body.plan)
    if not product_id:
        raise HTTPException(500, detail="DodoPayments 상품 ID가 설정되지 않았습니다.")

    if not settings.dodo_api_key:
        raise HTTPException(500, detail="DodoPayments API 키가 설정되지 않았습니다.")

    # 기존 활성 구독 처리 (업그레이드/중복 방지)
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "trial", "grace_period"]),
        )
    )
    now = datetime.now(timezone.utc)
    for existing_sub in existing_result.scalars().all():
        if existing_sub.status == "trial":
            existing_sub.status = "expired"
            existing_sub.updated_at = now
            logger.info("Trial 구독 만료 처리: user=%s → 유료 전환 진행", current_user.id)
        elif existing_sub.plan == body.plan:
            raise HTTPException(409, detail={"code": "ALREADY_SUBSCRIBED", "message": "이미 같은 플랜의 활성 구독이 있습니다."})
        else:
            existing_sub.status = "cancelled"
            existing_sub.cancelled_at = now
            existing_sub.updated_at = now
            logger.info(
                "기존 구독 취소: user=%s plan=%s → 새 플랜 %s 전환",
                current_user.id, existing_sub.plan, body.plan,
            )

    # DodoPayments Checkout Session 생성
    client = _get_dodo_client()
    session = client.checkout_sessions.create(
        product_cart=[{"product_id": product_id, "quantity": 1}],
        customer={"email": current_user.email or "", "name": current_user.display_name or ""},
        return_url="https://www.wewantpeace.live/upgrade/success",
        metadata={"user_id": str(current_user.id), "plan": body.plan},
    )

    logger.info(
        "DodoPayments checkout 생성: user=%s plan=%s product=%s",
        current_user.id, body.plan, product_id,
    )

    return {
        "checkout_url": session.checkout_url,
        "plan": body.plan,
    }


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

    # 기존 DodoPayments 구독이 있으면 업데이트
    existing = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if existing:
        existing.status = "active"
        existing.plan = plan
        existing.dodo_product_id = product_id
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
            dodo_subscription_id=dodo_sub_id,
            dodo_customer_id=customer.customer_id if customer else None,
            dodo_product_id=product_id,
            auto_renewing=not data.cancel_at_next_billing_date,
            started_at=now,
            expires_at=expires_at,
            next_billing_at=next_billing,
        )
        db.add(sub)

    # user.plan 변경
    user.plan = plan
    user.admin_plan_override = False
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
    """payment.succeeded: PaymentHistory 기록."""
    payment_id = data.payment_id
    dodo_sub_id = data.subscription_id

    # 구독 결제인 경우에만 기록
    if not dodo_sub_id:
        logger.info("DodoPayments 일회성 결제 성공 (구독 아님): payment_id=%s", payment_id)
        return

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
