"""tension_index에 convergence_bonus, anomaly_z 칼럼 추가

Revision ID: 0038
Revises: 0037
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"


def upgrade() -> None:
    op.add_column(
        "tension_index",
        sa.Column("convergence_bonus", sa.Float(), nullable=True, server_default="0"),
    )
    op.add_column(
        "tension_index",
        sa.Column("anomaly_z", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tension_index", "anomaly_z")
    op.drop_column("tension_index", "convergence_bonus")
