"""Add feedback to notifications for T12/T13

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("notifications")]

    if "feedback" not in columns:
        op.add_column(
            "notifications",
            sa.Column("feedback", sa.String(16), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("notifications", "feedback")
