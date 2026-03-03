"""Weekly KPI snapshot model for admin dashboard."""
from datetime import date, datetime, timezone
from sqlalchemy import Integer, String, Date, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class WeeklyKpiSnapshot(Base):
    __tablename__ = "weekly_kpi_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    kpi: Mapped[dict] = mapped_column(JSONB, nullable=False)
    wow_delta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    alerts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    data_source: Mapped[str] = mapped_column(String(16), default="auto")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
