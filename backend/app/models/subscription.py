from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.app.core.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    billing_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=699)
    currency: Mapped[str] = mapped_column(String(4), nullable=False, default="USD")
    billing_interval: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly", server_default="monthly",
    )
    # 스토어 IAP 필드 (promo:XXXX 형식 지원을 위해 32자)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    store_product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_transaction_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    store_original_transaction_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    auto_renewing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # DodoPayments 필드
    dodo_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dodo_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dodo_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 기간
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_billing_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    trial_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('active','cancelled','expired','trial','grace_period','billing_retry')", name="ck_subscriptions_status"),
        CheckConstraint("plan IN ('pro','pro_plus')", name="ck_subscriptions_plan"),
    )


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 웹훅 순서 역전(payment.succeeded가 subscription.active보다 먼저 도착) 시
    # 아직 user를 못 찾아도 매출을 버리지 않고 기록하기 위해 nullable.
    # subscription.active 처리 때 dodo_subscription_id로 백필됨.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(4), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    pg_transaction_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pg_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("status IN ('success','failed','refunded')", name="ck_payment_status"),
    )
