from datetime import datetime, timezone
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, TIMESTAMP, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("source_channels.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("source_type", "external_id", name="uq_raw_events_source_external"),
    )
