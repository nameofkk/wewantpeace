"""signal_matches 이력 테이블

시그널 ↔ 클러스터 매칭 이력을 추적.

Revision ID: 0048
Revises: 0047
"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"


def upgrade():
    op.create_table(
        "signal_matches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "signal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("signal_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Float, nullable=False),
        sa.Column("distance_km", sa.Float, nullable=True),
        sa.Column("time_delta_h", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_sm_cluster_created",
        "signal_matches",
        ["cluster_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_sm_signal", "signal_matches", ["signal_id"])


def downgrade():
    op.drop_index("ix_sm_signal", table_name="signal_matches")
    op.drop_index("ix_sm_cluster_created", table_name="signal_matches")
    op.drop_table("signal_matches")
