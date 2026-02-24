from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, ForeignKey, Integer, SmallInteger, String, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base, StringArray


class IssueCluster(Base):
    __tablename__ = "issue_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    cluster_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    geohash5: Mapped[str] = mapped_column(String(8), nullable=False)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_anchor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    title_ko: Mapped[str | None] = mapped_column(String, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    kscore: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_spike: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    spike_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source_tiers: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    independent_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_event_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ClusterEvent(Base):
    __tablename__ = "cluster_events"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("issue_clusters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("normalized_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
