"""cluster_key UNIQUE 제약, 인덱스 추가, comment parent_id FK

- issue_clusters.cluster_key: UNIQUE 제약 추가 (중복 제거 후)
- issue_clusters.is_active: 단일 인덱스 추가
- issue_clusters.kscore: 단일 인덱스 추가
- issue_clusters.severity: 단일 인덱스 추가
- issue_clusters (is_active, kscore): 복합 인덱스 추가
- comments.parent_id: FK → comments.id 추가

Revision ID: 0055
Revises: 0054
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. cluster_key UNIQUE 제약 추가 ──
    # 기존 중복 cluster_key 데이터 제거 (id가 작은 쪽 삭제)
    op.execute(
        sa.text(
            "DELETE FROM issue_clusters a USING issue_clusters b "
            "WHERE a.id < b.id AND a.cluster_key = b.cluster_key"
        )
    )
    op.create_unique_constraint(
        "uq_issue_clusters_cluster_key",
        "issue_clusters",
        ["cluster_key"],
    )

    # ── 2. 단일 인덱스 추가 ──
    op.create_index(
        "ix_issue_clusters_is_active",
        "issue_clusters",
        ["is_active"],
    )
    op.create_index(
        "ix_issue_clusters_kscore",
        "issue_clusters",
        ["kscore"],
    )
    op.create_index(
        "ix_issue_clusters_severity",
        "issue_clusters",
        ["severity"],
    )

    # ── 3. 복합 인덱스 추가 ──
    op.create_index(
        "ix_cluster_active_kscore",
        "issue_clusters",
        ["is_active", "kscore"],
    )

    # ── 4. comments.parent_id FK 추가 ──
    # 먼저 존재하지 않는 parent_id 참조를 NULL로 정리
    op.execute(
        sa.text(
            "UPDATE comments SET parent_id = NULL "
            "WHERE parent_id IS NOT NULL "
            "AND parent_id NOT IN (SELECT id FROM comments)"
        )
    )
    op.create_foreign_key(
        "fk_comments_parent_id",
        "comments",
        "comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_comments_parent_id", "comments", type_="foreignkey")
    op.drop_index("ix_cluster_active_kscore", table_name="issue_clusters")
    op.drop_index("ix_issue_clusters_severity", table_name="issue_clusters")
    op.drop_index("ix_issue_clusters_kscore", table_name="issue_clusters")
    op.drop_index("ix_issue_clusters_is_active", table_name="issue_clusters")
    op.drop_constraint("uq_issue_clusters_cluster_key", "issue_clusters", type_="unique")
