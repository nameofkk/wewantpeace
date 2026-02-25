"""플랫폼 통합 구독 관리 서비스 레이어."""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.models.user import User
from backend.app.core.store_products import (
    google_product_to_plan, apple_product_to_plan, PLAN_AMOUNTS,
)

logger = logging.getLogger(__name__)


async def _cancel_existing_active(user_id, db: AsyncSession) -> None:
    """기존 활성 구독 취소."""
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
    )
    for old_sub in existing.scalars().all():
        old_sub.status = "cancelled"
        old_sub.cancelled_at = datetime.now(timezone.utc)


async def activate_store_subscription(
    user_id,
    platform: str,
    product_id: str,
    transaction_id: str,
    original_transaction_id: str | None,
    expires_at: datetime | None,
    auto_renewing: bool,
    raw_response: dict,
    db: AsyncSession,
) -> Subscription:
    """스토어 IAP 구독 활성화 (Google/Apple 공통)."""
    # 상품 → 플랜 매핑
    if platform == "android":
        plan = google_product_to_plan(product_id)
    elif platform == "ios":
        plan = apple_product_to_plan(product_id)
    else:
        raise ValueError(f"Unknown platform: {platform}")

    if not plan:
        raise ValueError(f"Unknown product_id: {product_id}")

    amount = PLAN_AMOUNTS.get(plan, 0)
    now = datetime.now(timezone.utc)

    # 동일 original_transaction_id로 기존 구독 조회 (갱신인 경우)
    lookup_key = original_transaction_id or transaction_id
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.store_original_transaction_id == lookup_key,
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    existing_sub = existing_result.scalar_one_or_none()

    if existing_sub:
        # 기존 구독 갱신
        existing_sub.status = "active"
        existing_sub.store_transaction_id = transaction_id
        existing_sub.expires_at = expires_at
        existing_sub.auto_renewing = auto_renewing
        existing_sub.updated_at = now
        existing_sub.next_billing_at = expires_at
        sub = existing_sub
    else:
        # 기존 활성 구독 취소
        await _cancel_existing_active(user_id, db)

        # 새 구독 생성
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            platform=platform,
            store_product_id=product_id,
            store_transaction_id=transaction_id,
            store_original_transaction_id=lookup_key,
            auto_renewing=auto_renewing,
            amount=amount,
            started_at=now,
            expires_at=expires_at,
            next_billing_at=expires_at,
        )
        db.add(sub)

    # 결제 기록
    db.add(PaymentHistory(
        user_id=user_id,
        subscription_id=sub.id,
        amount=amount,
        status="success",
        platform=platform,
        pg_transaction_id=transaction_id,
        pg_response=raw_response,
    ))

    # User.plan 업데이트
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.plan = plan

    await db.flush()
    return sub


async def handle_store_event(
    platform: str,
    event_type: str,
    original_transaction_id: str,
    transaction_id: str | None,
    product_id: str | None,
    expires_at: datetime | None,
    auto_renewing: bool,
    raw_payload: dict,
    db: AsyncSession,
) -> dict:
    """스토어 웹훅 이벤트 처리 (갱신, 취소, 만료 등)."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.store_original_transaction_id == original_transaction_id,
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("Webhook: 구독 없음 original_tx=%s", original_transaction_id)
        return {"status": "subscription_not_found"}

    now = datetime.now(timezone.utc)

    # 이벤트 타입별 처리
    if event_type in ("RENEWED", "DID_RENEW", "SUBSCRIBED", "SUBSCRIPTION_STATE_ACTIVE"):
        sub.status = "active"
        if expires_at:
            sub.expires_at = expires_at
            sub.next_billing_at = expires_at
        if transaction_id:
            sub.store_transaction_id = transaction_id
        sub.auto_renewing = auto_renewing
        sub.updated_at = now

        # 결제 기록
        db.add(PaymentHistory(
            user_id=sub.user_id,
            subscription_id=sub.id,
            amount=sub.amount,
            status="success",
            platform=platform,
            pg_transaction_id=transaction_id or original_transaction_id,
            pg_response=raw_payload,
        ))

        # User.plan 갱신
        user_result = await db.execute(select(User).where(User.id == sub.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = sub.plan

    elif event_type in ("CANCELED", "EXPIRED", "DID_FAIL_TO_RENEW", "REVOKE",
                         "SUBSCRIPTION_STATE_EXPIRED", "SUBSCRIPTION_STATE_REVOKED"):
        sub.status = "expired"
        sub.auto_renewing = False
        sub.cancelled_at = now
        sub.updated_at = now

        # User.plan → free (만료일 지났으면)
        if not sub.expires_at or sub.expires_at <= now:
            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = "free"

    elif event_type in ("IN_GRACE_PERIOD", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
        sub.status = "grace_period"
        sub.auto_renewing = auto_renewing
        sub.updated_at = now

    elif event_type in ("ON_HOLD", "SUBSCRIPTION_STATE_ON_HOLD"):
        sub.status = "billing_retry"
        sub.auto_renewing = False
        sub.updated_at = now

    elif event_type == "REFUND":
        sub.status = "expired"
        sub.auto_renewing = False
        sub.updated_at = now
        db.add(PaymentHistory(
            user_id=sub.user_id,
            subscription_id=sub.id,
            amount=sub.amount,
            status="refunded",
            platform=platform,
            pg_transaction_id=transaction_id or original_transaction_id,
            pg_response=raw_payload,
        ))
        # User.plan → free
        user_result = await db.execute(select(User).where(User.id == sub.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = "free"
    else:
        logger.info("Webhook: 미처리 이벤트 type=%s", event_type)
        return {"status": "ignored", "event_type": event_type}

    await db.flush()
    return {"status": "ok", "event_type": event_type, "subscription_id": str(sub.id)}
