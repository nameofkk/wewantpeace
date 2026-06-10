from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, TIMESTAMP, text
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
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
        # 같은 결제건이 두 번 적재되는 걸 DB 차원에서 막는 백스톱.
        # 웹훅 재전송 / sync 백필이 겹치면 같은 (platform, pg_transaction_id, status)
        # 행이 두 번 들어가서 매출이 부풀려지던 버그가 있었음.
        # status까지 키에 넣은 이유: 같은 거래의 success → refunded 처럼
        # 상태가 다른 정상 기록은 막으면 안 되니까.
        # pg_transaction_id 없는(NULL) 레거시/내부 기록은 여러 개 허용(부분 인덱스).
        Index(
            "uq_payment_history_pg_txn",
            "platform", "pg_transaction_id", "status",
            unique=True,
            postgresql_where=text("pg_transaction_id IS NOT NULL"),
        ),
    )
