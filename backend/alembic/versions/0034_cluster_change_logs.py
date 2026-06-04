"""Add cluster_change_logs table for T15 correction log

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = inspector.get_table_names()

    if "cluster_change_logs" not in existing:
        op.create_table(
            "cluster_change_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("cluster_id", sa.Uuid(as_uuid=True), sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("field", sa.String(32), nullable=False),
            sa.Column("old_value", sa.String(), nullable=True),
            sa.Column("new_value", sa.String(), nullable=True),
            sa.Column("reason", sa.String(256), nullable=False, server_default="system"),
            sa.Column("updated_by", sa.String(64), nullable=False, server_default="system"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("cluster_change_logs")
