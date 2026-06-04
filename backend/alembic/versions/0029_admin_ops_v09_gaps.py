"""admin ops v0.9 gap fixes - partner status/url/last_published_at, kpi data_source

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    # ── partners: status default prospect, add url & last_published_at ──
    if "partners" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("partners")}

        # Change status default from 'lead' to 'prospect'
        op.alter_column(
            "partners", "status",
            server_default="prospect",
        )

        if "url" not in columns:
            op.add_column(
                "partners",
                sa.Column("url", sa.String(512), nullable=True),
            )

        if "last_published_at" not in columns:
            op.add_column(
                "partners",
                sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
            )

    # ── weekly_kpi_snapshots: add data_source ──
    if "weekly_kpi_snapshots" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("weekly_kpi_snapshots")}

        if "data_source" not in columns:
            op.add_column(
                "weekly_kpi_snapshots",
                sa.Column("data_source", sa.String(16), server_default="auto"),
            )


def downgrade() -> None:
    op.drop_column("weekly_kpi_snapshots", "data_source")
    op.drop_column("partners", "last_published_at")
    op.drop_column("partners", "url")
    op.alter_column("partners", "status", server_default="lead")
