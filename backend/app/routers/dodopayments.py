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
from sqlalchemy.exc import IntegrityError
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


def _normalize_tx_id(pg_transaction_id: str | None) -> str | None:
    """tx id를 정규화한다 — 빈 문자열·공백만 있는 값은 전부 None 하나로 모은다.

    멱등 키로 못 쓰는 값('', '   ', None)을 None 한 가지로 통일하는 이유:
    payment_history엔 (platform, pg_transaction_id, status) 부분 유니크 인덱스가
    'WHERE pg_transaction_id IS NOT NULL'로 걸려 있다. 그런데 빈 문자열 ''은 NULL이
    아니라서 인덱스가 '진짜 키'로 잡는다. 그러면 tx id 없이 들어오는 서로 다른 갱신
    결제들이 전부 같은 '' 키로 충돌해서, 멱등 사전체크는 스킵되는데(아래 not 가드) DB
    인덱스는 막아버리는 엇갈린 상태가 된다. 정규화로 ''→None을 만들어서 '키 없는 결제'는
    인덱스에서도 일관되게 빠지게(IS NULL) 하고, 멱등 체크도 똑같이 스킵되게 맞춘다.
    """
    if pg_transaction_id is None:
        return None
    stripped = pg_transaction_id.strip()
    return stripped or None


async def _payment_already_recorded(db: AsyncSession, payment_id: str | None) -> bool:
    """이 dodo payment_id가 이미 success로 적재됐는지 확인.

    웹훅 재전송 / sync 백필이 같은 결제건을 두 번 넣어서 매출이 부풀려지던 걸 막는다.
    dodo payment_id는 결제 1건당 고유하고, 웹훅은 success만 적재하므로 status=success로 본다.
    """
    payment_id = _normalize_tx_id(payment_id)
    if not payment_id:
        return False
    result = await db.execute(
        select(PaymentHistory.id).where(
            PaymentHistory.platform == "dodopayments",
            PaymentHistory.pg_transaction_id == payment_id,
            PaymentHistory.status == "success",
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _payment_created_at(data) -> datetime:
    """웹훅 결제 데이터에서 실제 결제시각을 뽑는다.

    Dodo Payment 객체의 created_at(결제가 일어난 시각, timezone-aware)을 그대로 쓴다.
    이게 PaymentHistory.created_at에 들어가야 매출 집계가 '처리 시각'이 아닌 '실제 결제
    시각' 기준으로 잡힌다. 웹훅 재전송이 며칠 늦게 와도 매출 날짜가 안 밀린다.
    값이 없거나(이론상) tz 정보가 빠지면 안전하게 now()로 폴백한다.
    """
    ts = getattr(data, "created_at", None)
    if isinstance(ts, datetime):
        # tz 없는 naive 값이 오면 UTC로 간주 (DB 컬럼이 timezone-aware라 비교 깨짐 방지)
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    return datetime.now(timezone.utc)


async def _resolve_user_for_payment(data, db: AsyncSession) -> User | None:
    """결제/구독 웹훅 데이터에서 사용자를 찾는다.

    우선순위: metadata.user_id(체크아웃 때 우리가 직접 심은 값) → customer 이메일 폴백.
    구독을 못 찾아 결제행을 보존(subscription_id=NULL)할 때 PaymentHistory.user_id는
    NOT NULL이라 반드시 사용자를 특정해야 해서 둔 헬퍼.
    """
    metadata = getattr(data, "metadata", None) or {}
    user_id_str = metadata.get("user_id", "") if isinstance(metadata, dict) else ""
    if user_id_str:
        try:
            uid = _uuid.UUID(str(user_id_str))
        except (ValueError, TypeError):
            uid = None
        if uid is not None:
            res = await db.execute(select(User).where(User.id == uid))
            user = res.scalar_one_or_none()
            if user:
                return user

    customer = getattr(data, "customer", None)
    email = getattr(customer, "email", None) if customer else None
    if email:
        res = await db.execute(select(User).where(User.email == email).limit(1))
        user = res.scalar_one_or_none()
        if user:
            return user
    return None


async def _link_orphan_payments(db: AsyncSession, sub: Subscription) -> int:
    """subscription_id=NULL로 보존된 고아 결제행을 이 구독에 뒤늦게 연결.

    payment.succeeded가 subscription.active보다 먼저 도착하면(도착 순서 미보장) 구독을
    못 찾아 결제행을 subscription_id=NULL로 보존해 둔다. 이후 구독이 만들어지면
    (subscription.active 웹훅이든 sync든) 이 함수가 pg_response의 dodo_subscription_id로
    매칭해서 subscription_id를 채운다.

    매출은 payment_history.status=success 기준이라 NULL 상태로도 매출엔 이미 잡히지만,
    구독별 분석·환불 연계를 위해 연결까지 맞춰 준다. 연결한 행 수를 돌려준다.
    """
    dsid = sub.dodo_subscription_id
    if not dsid:
        return 0
    # JSON 경로 연산자는 SQLite/Postgres 호환이 어긋날 수 있어, 후보를 좁게(같은 유저의
    # 미연결 dodo 결제) 뽑은 뒤 파이썬에서 dodo_subscription_id를 대조한다.
    result = await db.execute(
        select(PaymentHistory).where(
            PaymentHistory.subscription_id.is_(None),
            PaymentHistory.platform == "dodopayments",
            PaymentHistory.user_id == sub.user_id,
        )
    )
    linked = 0
    for row in result.scalars().all():
        meta = row.pg_response or {}
        if isinstance(meta, dict) and meta.get("dodo_subscription_id") == dsid:
            row.subscription_id = sub.id
            linked += 1
    if linked:
        await db.flush()
        logger.info("DodoPayments 보존된 고아 결제행 연결: dodo_sub=%s count=%d", dsid, linked)
    return linked


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

    # 중복 구독 방지 (같은 플랜·주기 이미 활성 시 409)
    # ⚠ 기존 구독은 여기서 취소하지 않음 — 체크아웃 미완료 시 기존 구독이 사라지는 버그 방지
    # 플랜 전환 시 기존 구독 정리는 subscription.active 웹훅(_handle_subscription_active)에서 수행
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "grace_period"]),
        )
    )
    for existing_sub in existing_result.scalars().all():
        if existing_sub.plan == body.plan and existing_sub.billing_interval == body.billing_interval:
            raise HTTPException(409, detail="이미 같은 플랜·결제 주기의 활성 구독이 있습니다.")

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

    # 중복 구독 방지 — 기존 구독 취소는 subscription.active 웹훅에서 처리
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "grace_period"]),
        )
    )
    for existing_sub in existing_result.scalars().all():
        if existing_sub.plan == plan and existing_sub.billing_interval == billing_interval:
            raise HTTPException(409, detail="이미 같은 플랜·결제 주기의 활성 구독이 있습니다.")

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
    elif event_type == "refund.succeeded":
        await _handle_refund_succeeded(event.data, db)
    elif event_type == "refund.failed":
        logger.info("DodoPayments 환불 실패 이벤트: payment_id=%s", getattr(event.data, "payment_id", "?"))
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
    billing_interval = _dodo_product_to_billing_interval(product_id)

    # monthly/annual은 Dodo의 expires_at 대신 next_billing을 사용
    # (Dodo가 monthly 구독에 expires_at=2045 같은 이상한 값을 보내는 경우 방어)
    if billing_interval in ("monthly", "annual"):
        expires_at = next_billing
    else:
        expires_at = data.expires_at or next_billing

    # 기존 DodoPayments 구독이 있으면 업데이트
    existing = await _find_sub_by_dodo_id(dodo_sub_id, db)
    if existing:
        existing.status = "active"
        existing.plan = plan
        existing.dodo_product_id = product_id
        existing.billing_interval = billing_interval
        existing.expires_at = expires_at if billing_interval != "lifetime" else None
        existing.next_billing_at = next_billing if billing_interval != "lifetime" else None
        existing.started_at = now
        existing.cancelled_at = None
        existing.auto_renewing = not data.cancel_at_next_billing_date if billing_interval != "lifetime" else False
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

    target_sub = existing if existing else sub

    # 기존 trial/active 구독 만료 처리 (체크아웃 시작이 아닌 결제 확정 시점에 정리)
    new_sub_id = target_sub.id
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

    # payment.succeeded가 먼저 와서 subscription_id=NULL로 보존돼 있던 결제행을 이 구독에 연결
    # (이벤트 순서 역전 복구). flush로 새 구독을 먼저 insert해 FK가 유효하게 한 뒤 연결.
    await db.flush()
    await _link_orphan_payments(db, target_sub)

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

    # monthly/annual은 Dodo의 expires_at 대신 next_billing 사용 (2045 버그 방어)
    if sub.billing_interval in ("monthly", "annual"):
        expires_at = next_billing
    else:
        expires_at = data.expires_at or next_billing

    sub.status = "active"
    sub.expires_at = expires_at
    sub.next_billing_at = next_billing
    sub.started_at = now  # 실결제일 갱신
    sub.cancelled_at = None  # 갱신 시 취소 플래그 초기화
    sub.auto_renewing = True
    sub.updated_at = now
    await db.flush()

    # PaymentHistory는 payment.succeeded 이벤트에서 기록 (중복 방지)
    logger.info("DodoPayments 구독 갱신: dodo_sub=%s expires_at=%s started_at=%s", dodo_sub_id, expires_at, now)


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


async def _handle_refund_succeeded(data, db: AsyncSession) -> None:
    """refund.succeeded: 환불된 만큼 매출에서 빼고, 전액 환불이면 등급도 회수한다.

    매출(monthly_revenue)은 payment_history에서 status='success'인 행의 amount만
    더하는 구조다. 그래서 환불을 이렇게 반영한다.
    - 전액 환불: 원결제 success 행을 refunded로 바꿔서 매출에서 통째로 빠지게 + 등급 free 회수.
    - 부분 환불: success 행 amount를 환불액만큼 깎아서 매출이 딱 그만큼만 줄게(등급 유지).
    이렇게 해야 1달러 부분 환불에 699달러 매출이 통째로 날아가는 과차감을 막는다.
    """
    payment_id = getattr(data, "payment_id", None)
    refund_amount = getattr(data, "amount", None)
    if not payment_id:
        logger.warning("DodoPayments refund: payment_id 누락 (data=%s)", data)
        return

    # 원결제 success 행 조회
    result = await db.execute(
        select(PaymentHistory).where(
            PaymentHistory.platform == "dodopayments",
            PaymentHistory.pg_transaction_id == payment_id,
            PaymentHistory.status == "success",
        ).limit(1)
    )
    paid = result.scalar_one_or_none()

    if paid is None:
        # 이미 refunded로 바뀌었거나(웹훅 재전송), success 기록 자체가 없던 결제
        already = await db.execute(
            select(PaymentHistory.id).where(
                PaymentHistory.platform == "dodopayments",
                PaymentHistory.pg_transaction_id == payment_id,
                PaymentHistory.status == "refunded",
            ).limit(1)
        )
        if already.scalar_one_or_none() is not None:
            logger.info("DodoPayments refund: 이미 환불 처리됨, 건너뜀 payment_id=%s", payment_id)
        else:
            logger.warning("DodoPayments refund: 원결제 기록 없음 payment_id=%s", payment_id)
        return

    sub_id = paid.subscription_id
    paid_amount = paid.amount

    # 전액 환불 판정. refund amount가 없으면(전액 환불 이벤트가 금액을 안 주는 경우) 전액으로 본다.
    is_full = refund_amount is None or refund_amount >= paid_amount

    if is_full:
        # success → refunded 갱신.
        # savepoint로 감싸서, 같은 거래의 refunded 행이 이미 있던 비정상 데이터라
        # 유니크 인덱스(platform, pg_transaction_id, status)에 걸려도 500 안 내고 정리한다.
        try:
            async with db.begin_nested():
                paid.status = "refunded"
                await db.flush()
        except IntegrityError:
            logger.info(
                "DodoPayments refund: refunded 행 이미 존재 → 중복 success 행 제거 payment_id=%s",
                payment_id,
            )
            await db.delete(paid)
            await db.flush()
    else:
        # 부분 환불: 매출에서 환불액만큼만 차감(등급은 유지)
        paid.amount = max(0, paid_amount - refund_amount)
        await db.flush()

    # 전액 환불일 때만 구독·유저 등급 회수
    if is_full and sub_id:
        sub_result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = sub_result.scalar_one_or_none()
        if sub and sub.status != "expired":
            now = datetime.now(timezone.utc)
            sub.status = "expired"
            sub.auto_renewing = False
            sub.updated_at = now

            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            if user and not user.admin_plan_override:
                user.plan = "free"
                await sync_area_activation(user.id, "free", db)
            await db.flush()

    logger.info(
        "DodoPayments 환불 처리 완료: payment_id=%s full=%s sub=%s",
        payment_id, is_full, sub_id,
    )


async def _handle_payment_succeeded(data, db: AsyncSession) -> None:
    """payment.succeeded: PaymentHistory 기록 + lifetime 일회성 결제 처리."""
    # 빈/공백 tx id는 None으로 정규화 — 멱등 사전체크와 DB 부분 유니크 인덱스가
    # '키 없는 결제'를 똑같이(IS NULL) 취급하게 맞춰서, tx id 빠진 갱신 결제가
    # 인덱스에 '' 키로 충돌하거나 매출이 부풀려지는 엇갈린 상태를 막는다.
    payment_id = _normalize_tx_id(data.payment_id)
    dodo_sub_id = getattr(data, "subscription_id", None)

    # 멱등성 가드: 같은 결제(payment_id)가 이미 적재됐으면 통째로 건너뜀.
    # 웹훅이 여러 번 와도(재전송), sync 백필이랑 겹쳐도 PaymentHistory가 두 번 안 들어가게.
    # lifetime 경로의 구독 중복 생성까지 여기서 같이 막힌다.
    if payment_id and await _payment_already_recorded(db, payment_id):
        logger.info("DodoPayments payment_succeeded: 이미 기록된 결제 건너뜀 payment_id=%s", payment_id)
        return

    paid_at = _payment_created_at(data)

    # 구독 결제인 경우: PaymentHistory만 기록 (구독 활성화는 subscription.active에서 처리)
    if dodo_sub_id:
        sub = await _find_sub_by_dodo_id(dodo_sub_id, db)
        if sub:
            history_user_id = sub.user_id
            history_sub_id = sub.id
            history_plan = sub.plan
            pg_response = None
        else:
            # 구독을 아직 못 찾음 — payment.succeeded가 subscription.active보다 먼저 도착하는
            # 이벤트 순서 역전이나 활성화 웹훅 유실로 흔히 생긴다. 예전엔 여기서 결제행을
            # 통째로 버려서(return) 매출이 영영 누락됐다. 이제는 user를 특정해
            # subscription_id=NULL로 결제행을 보존하고, dodo_subscription_id를 pg_response에
            # 남겨 뒤늦게 구독이 생기면(subscription.active 웹훅 / sync) _link_orphan_payments가
            # 연결하도록 한다. 매출(success 합산)은 NULL 상태로도 곧장 잡힌다.
            user = await _resolve_user_for_payment(data, db)
            if user is None:
                logger.warning(
                    "DodoPayments payment_succeeded: 구독·사용자 모두 못 찾아 보존 불가 dodo_sub=%s payment=%s",
                    dodo_sub_id, payment_id,
                )
                return
            history_user_id = user.id
            history_sub_id = None
            history_plan = (getattr(data, "metadata", None) or {}).get("plan", "unknown")
            pg_response = {"dodo_subscription_id": dodo_sub_id, "unlinked": True}
            logger.warning(
                "DodoPayments payment_succeeded: 구독 미발견 → 결제행 보존(subscription_id=NULL) "
                "dodo_sub=%s payment=%s user=%s",
                dodo_sub_id, payment_id, user.id,
            )

        history = PaymentHistory(
            user_id=history_user_id,
            subscription_id=history_sub_id,
            amount=data.total_amount,
            currency=str(data.currency),
            status="success",
            platform="dodopayments",
            pg_transaction_id=payment_id,
            pg_response=pg_response,
            created_at=paid_at,
        )
        # savepoint로 감싸서 동시 웹훅 경합(둘 다 사전 체크 통과)으로 유니크 인덱스가
        # 걸려도 500 안 내고 멱등하게 넘어감. 사전 체크가 1차, 이게 최종 방어선.
        try:
            async with db.begin_nested():
                db.add(history)
        except IntegrityError:
            logger.info("DodoPayments payment_succeeded: 동시 적재 경합 감지, 건너뜀 payment_id=%s", payment_id)
            return

        # 퍼널 계측: 유료전환 (최초 1회 — 갱신 결제는 중복 적재 안 됨)
        from backend.app.services.funnel import log_funnel_event, EV_PAID
        await log_funnel_event(db, EV_PAID, history_user_id, props={"plan": history_plan, "platform": "dodopayments"}, once=True)

        await db.flush()

        logger.info(
            "DodoPayments 결제 성공 기록: payment_id=%s dodo_sub=%s linked=%s",
            payment_id, dodo_sub_id, history_sub_id is not None,
        )
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
        created_at=paid_at,
    )
    db.add(history)

    # user.plan 업데이트
    if not user.admin_plan_override:
        user.plan = plan
        await sync_area_activation(user_id, plan, db)

    # 퍼널 계측: 유료전환 (최초 1회)
    from backend.app.services.funnel import log_funnel_event, EV_PAID
    await log_funnel_event(db, EV_PAID, user_id, props={"plan": plan, "platform": "dodopayments", "billing": "lifetime"}, once=True)

    await db.flush()

    logger.info(
        "DodoPayments lifetime 결제 처리 완료: user=%s plan=%s payment=%s",
        user_id, plan, payment_id,
    )
