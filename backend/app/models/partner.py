"""Partner CRM model."""
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import String, Text, Date, TIMESTAMP, Uuid, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_type: Mapped[str] = mapped_column(String(32), default="media")
    status: Mapped[str] = mapped_column(String(16), default="prospect")
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_partners_status", "status"),
        Index("ix_partners_follow_up", "next_follow_up", postgresql_where="next_follow_up IS NOT NULL"),
    )
