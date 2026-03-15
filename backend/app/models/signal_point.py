from datetime import datetime, timezone
from sqlalchemy import Float, ForeignKey, Index, String, TIMESTAMP, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base


class SignalPoint(Base):
    __tablename__ = "signal_points"
    __table_args__ = (
        Index("ix_sp_type_observed", "signal_type", "observed_at"),
        Index("ix_sp_country_observed", "country_code", "observed_at"),
        Index("ix_sp_expires", "expires_at"),
        Index("ix_sp_external_id", "external_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    raw_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    matched_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("issue_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_time_delta_h: Mapped[float | None] = mapped_column(Float, nullable=True)
