from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, Index, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base, StringArray


class TrendingKeyword(Base):
    __tablename__ = "trending_keywords"
    __table_args__ = (
        Index("ix_trending_kw_scope_nkw_calcat", "scope", "normalized_kw", "calculated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    keyword_ko: Mapped[str | None] = mapped_column(String(256), nullable=True)
    normalized_kw: Mapped[str] = mapped_column(String(256), nullable=False)
    kscore: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    topic: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_codes: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    cluster_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_spike: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    valid_until: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
