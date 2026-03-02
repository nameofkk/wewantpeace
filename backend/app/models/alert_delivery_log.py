from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, ForeignKey, String, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class AlertDeliveryLog(Base):
    __tablename__ = "alert_delivery_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cluster_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False)
    spike_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("spike_events.id", ondelete="SET NULL"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(16), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    suppression_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    pipeline_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="shadow")
    collapse_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("decision IN ('pending','sent','failed','suppressed')", name="ck_delivery_decision"),
        CheckConstraint("pipeline_mode IN ('shadow','primary')", name="ck_pipeline_mode"),
    )
