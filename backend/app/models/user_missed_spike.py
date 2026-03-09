from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class UserMissedAlertSummary(Base):
    """v7: UserMissedSpikeSummary → UserMissedAlertSummary"""
    __tablename__ = "user_missed_alert_summary"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cluster_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False)
    alert_cluster_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    is_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


# 하위호환 alias
UserMissedSpikeSummary = UserMissedAlertSummary
