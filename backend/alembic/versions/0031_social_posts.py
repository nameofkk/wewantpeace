"""Add social_posts and social_post_platform tables

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = inspector.get_table_names()

    if "social_posts" not in existing:
        op.create_table(
            "social_posts",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("content_type", sa.String(32), nullable=False),
            sa.Column("lang", sa.String(4), nullable=False),
            sa.Column("body_text", sa.Text, nullable=False),
            sa.Column("hashtags", sa.ARRAY(sa.String), nullable=False, server_default="{}"),
            sa.Column("image_url", sa.String(1024), nullable=True),
            sa.Column("risk_level", sa.String(8), nullable=False, server_default="medium"),
            sa.Column(
                "source_cluster_id", sa.Uuid(as_uuid=True),
                sa.ForeignKey("issue_clusters.id", ondelete="SET NULL"), nullable=True,
            ),
            sa.Column(
                "source_spike_id", sa.Uuid(as_uuid=True),
                sa.ForeignKey("spike_events.id", ondelete="SET NULL"), nullable=True,
            ),
            sa.Column("dedup_key", sa.String(128), nullable=False, unique=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending_review"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("approved_by", sa.String(64), nullable=True),
            sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index("ix_social_posts_status_created", "social_posts", ["status", "created_at"])
        op.create_index("ix_social_posts_content_type", "social_posts", ["content_type"])

    if "social_post_platform" not in existing:
        op.create_table(
            "social_post_platform",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "post_id", sa.Uuid(as_uuid=True),
                sa.ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("platform", sa.String(16), nullable=False),
            sa.Column("platform_post_id", sa.String(256), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.UniqueConstraint("post_id", "platform", name="uq_social_post_platform"),
        )


def downgrade() -> None:
    op.drop_table("social_post_platform")
    op.drop_table("social_posts")
