"""Add sub_topic to normalized_events and issue_clusters

클러스터링 개선: sub-topic soft signal을 위한 컬럼 추가.
- normalized_events.sub_topic VARCHAR(32) DEFAULT 'general'
- issue_clusters.sub_topic VARCHAR(32) DEFAULT 'general'
- 인덱스: ix_clusters_key_subtopic on (cluster_key, sub_topic)

Revision ID: 0054
Revises: 0053
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "normalized_events",
        sa.Column("sub_topic", sa.String(32), nullable=False, server_default="general"),
    )
    op.add_column(
        "issue_clusters",
        sa.Column("sub_topic", sa.String(32), nullable=False, server_default="general"),
    )
    op.create_index(
        "ix_clusters_key_subtopic",
        "issue_clusters",
        ["cluster_key", "sub_topic"],
    )


def downgrade() -> None:
    op.drop_index("ix_clusters_key_subtopic", table_name="issue_clusters")
    op.drop_column("issue_clusters", "sub_topic")
    op.drop_column("normalized_events", "sub_topic")
