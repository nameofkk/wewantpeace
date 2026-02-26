from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, ForeignKey, SmallInteger, String, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base


class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("raw_events.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    title_ko: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_anchor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    geohash5: Mapped[str | None] = mapped_column(String(8), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    source_tier: Mapped[str] = mapped_column(String(1), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    translation_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ok | failed | skipped
    geo_method: Mapped[str | None] = mapped_column(String(16), nullable=True)  # keyword | geocoder | fallback | none
    event_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
