"""signal_points 테이블 + issue_clusters 신호 컬럼 추가

SignalPoint: FIRMS/IODA/Cloudflare/GPS 등 외부 신호 데이터
issue_clusters에 signal_corroboration_count, signal_types 컬럼 추가

Revision ID: 0047
Revises: 0046
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "0047"
down_revision = "0046"


def upgrade():
    op.create_table(
        "signal_points",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("signal_type", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("country_code", sa.String(4), nullable=True),
        sa.Column("intensity", sa.Float, nullable=False, server_default="0"),
        sa.Column("raw_value", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "matched_cluster_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("issue_clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("match_distance_km", sa.Float, nullable=True),
        sa.Column("match_time_delta_h", sa.Float, nullable=True),
        sa.UniqueConstraint("external_id", name="uq_signal_points_external_id"),
    )

    op.create_index("ix_sp_type_observed", "signal_points", ["signal_type", sa.text("observed_at DESC")])
    op.create_index("ix_sp_country_observed", "signal_points", ["country_code", sa.text("observed_at DESC")])
    op.create_index("ix_sp_expires", "signal_points", ["expires_at"])
    op.create_index("ix_sp_external_id", "signal_points", ["external_id"], unique=True)

    # issue_clusters에 신호 관련 컬럼 추가
    op.add_column("issue_clusters", sa.Column("signal_corroboration_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("issue_clusters", sa.Column("signal_types", ARRAY(sa.String), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("issue_clusters", "signal_types")
    op.drop_column("issue_clusters", "signal_corroboration_count")

    op.drop_index("ix_sp_external_id", table_name="signal_points")
    op.drop_index("ix_sp_expires", table_name="signal_points")
    op.drop_index("ix_sp_country_observed", table_name="signal_points")
    op.drop_index("ix_sp_type_observed", table_name="signal_points")
    op.drop_table("signal_points")
