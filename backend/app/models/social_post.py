from datetime import datetime, timezone
from sqlalchemy import (
    ForeignKey, Index, String, Text, TIMESTAMP, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base, StringArray


class SocialPost(Base):
    __tablename__ = "social_posts"
    __table_args__ = (
        Index("ix_social_posts_status_created", "status", "created_at"),
        Index("ix_social_posts_content_type", "content_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    lang: Mapped[str] = mapped_column(String(4), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Threads 게시 직후 다는 댓글 (출처 목록). 없으면 댓글 없음
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # 카드뉴스(캐러셀) 장별 이미지. 2장 이상이면 Threads 에 CAROUSEL 로 올린다. image_url 은 표지
    image_urls: Mapped[list[str] | None] = mapped_column(StringArray, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False, default="medium")
    source_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("issue_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_spike_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("spike_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending_review")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class SocialPostPlatform(Base):
    __tablename__ = "social_post_platform"
    __table_args__ = (
        UniqueConstraint("post_id", "platform", name="uq_social_post_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    platform_post_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
