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
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=4900)
    currency: Mapped[str] = mapped_column(String(4), nullable=False, default="KRW")
    # 스토어 IAP 필드
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    store_product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_transaction_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    store_original_transaction_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    auto_renewing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 기간
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_billing_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("status IN ('active','cancelled','expired','trial','grace_period','billing_retry')", name="ck_subscriptions_status"),
        CheckConstraint("plan IN ('pro','pro_plus')", name="ck_subscriptions_plan"),
    )


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(4), nullable=False, default="KRW")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    pg_transaction_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pg_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("status IN ('success','failed','refunded')", name="ck_payment_status"),
    )
