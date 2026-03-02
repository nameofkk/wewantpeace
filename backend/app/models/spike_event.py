from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Float, ForeignKey, Integer, SmallInteger, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class SpikeEvent(Base):
    __tablename__ = "spike_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kscore: Mapped[float] = mapped_column(Float, nullable=False)
    c1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    c10: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unique_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
