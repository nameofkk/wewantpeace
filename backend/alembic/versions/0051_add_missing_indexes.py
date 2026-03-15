"""Add missing indexes and FK constraints

- normalized_events: is_duplicate, severity, raw_event_id 인덱스 추가
- alert_delivery_log: (user_id, cluster_id, created_at) 복합 인덱스 추가
- posts: cluster_id → issue_clusters.id FK 추가

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── normalized_events 인덱스 ──
    op.create_index(
        "ix_normalized_events_is_duplicate",
        "normalized_events",
        ["is_duplicate"],
    )
    op.create_index(
        "ix_normalized_events_severity",
        "normalized_events",
        ["severity"],
    )
    op.create_index(
        "ix_normalized_events_raw_event_id",
        "normalized_events",
        ["raw_event_id"],
    )

    # ── alert_delivery_log 복합 인덱스 (중복 알림 체크용) ──
    op.create_index(
        "ix_alert_delivery_log_user_cluster_created",
        "alert_delivery_log",
        ["user_id", "cluster_id", "created_at"],
    )

    # ── posts.cluster_id FK → issue_clusters.id ──
    op.create_foreign_key(
        "fk_posts_cluster_id",
        "posts",
        "issue_clusters",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_posts_cluster_id", "posts", type_="foreignkey")
    op.drop_index("ix_alert_delivery_log_user_cluster_created", "alert_delivery_log")
    op.drop_index("ix_normalized_events_raw_event_id", "normalized_events")
    op.drop_index("ix_normalized_events_severity", "normalized_events")
    op.drop_index("ix_normalized_events_is_duplicate", "normalized_events")
