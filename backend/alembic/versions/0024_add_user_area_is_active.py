"""add is_active column to user_areas

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("user_areas")]
    if "is_active" not in columns:
        op.add_column(
            "user_areas",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index(
            "ix_user_areas_active",
            "user_areas",
            ["user_id", "country_code"],
            postgresql_where=sa.text("is_active = true"),
        )


def downgrade() -> None:
    op.drop_index("ix_user_areas_active", table_name="user_areas")
    op.drop_column("user_areas", "is_active")
