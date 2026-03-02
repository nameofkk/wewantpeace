"""Generic application event for KPI tracking."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, TIMESTAMP, Uuid, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class AppEvent(Base):
    __tablename__ = "app_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    props: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_app_events_name_created", "name", "created_at"),
        Index("ix_app_events_user", "user_id", "name", "created_at"),
    )
