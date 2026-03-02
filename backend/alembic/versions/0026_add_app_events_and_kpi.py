"""add app_events table for KPI tracking

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "app_events" not in existing_tables:
        op.create_table(
            "app_events",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("user_id", UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("session_id", sa.String(64), nullable=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("props", JSONB(), nullable=True),
            sa.Column("platform", sa.String(16), nullable=False, server_default="web"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_app_events_name_created", "app_events", ["name", "created_at"])
        op.create_index("ix_app_events_user", "app_events", ["user_id", "name", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_app_events_user", table_name="app_events")
    op.drop_index("ix_app_events_name_created", table_name="app_events")
    op.drop_table("app_events")
