"""user_preferences: min_kscore 컬럼 추가

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("min_kscore", sa.Float(), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "min_kscore")
