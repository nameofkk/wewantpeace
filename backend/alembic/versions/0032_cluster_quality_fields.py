"""Add is_active and is_flagged to issue_clusters for pipeline quality

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("issue_clusters")]

    if "is_active" not in columns:
        op.add_column(
            "issue_clusters",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

    if "is_flagged" not in columns:
        op.add_column(
            "issue_clusters",
            sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    op.drop_column("issue_clusters", "is_flagged")
    op.drop_column("issue_clusters", "is_active")
