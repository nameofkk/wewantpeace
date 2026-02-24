from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Float, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base, StringArray


class SourceChannel(Base):
    __tablename__ = "source_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    tier: Mapped[str] = mapped_column(String(1), nullable=False)
    base_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    language: Mapped[str] = mapped_column(String(8), nullable=True, default="en")
    topics: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    geo_focus: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="telegram")
    feed_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    __table_args__ = (
        CheckConstraint("tier IN ('A','B','C','D')", name="ck_source_channels_tier"),
    )
