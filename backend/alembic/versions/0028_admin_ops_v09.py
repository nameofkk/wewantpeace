"""admin ops v0.9 - weekly KPI snapshots, partners CRM, short links

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── weekly_kpi_snapshots ──
    if "weekly_kpi_snapshots" not in existing_tables:
        op.create_table(
            "weekly_kpi_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("week_end", sa.Date(), nullable=False),
            sa.Column("metrics", JSONB(), nullable=False),
            sa.Column("kpi", JSONB(), nullable=False),
            sa.Column("wow_delta", JSONB(), nullable=True),
            sa.Column("alerts", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("uq_weekly_kpi_week", "weekly_kpi_snapshots", ["week_start"], unique=True)

    # ── partners ──
    if "partners" not in existing_tables:
        op.create_table(
            "partners",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("contact_name", sa.String(64), nullable=True),
            sa.Column("contact_email", sa.String(256), nullable=True),
            sa.Column("contact_phone", sa.String(32), nullable=True),
            sa.Column("company_type", sa.String(32), server_default="media"),
            sa.Column("status", sa.String(16), server_default="lead"),
            sa.Column("channel", sa.String(32), nullable=True),
            sa.Column("segment", sa.String(32), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("next_follow_up", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_partners_status", "partners", ["status"])
        op.execute(
            "CREATE INDEX ix_partners_follow_up ON partners(next_follow_up) "
            "WHERE next_follow_up IS NOT NULL"
        )

    # ── short_links ──
    if "short_links" not in existing_tables:
        op.create_table(
            "short_links",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("code", sa.String(16), nullable=False, unique=True),
            sa.Column("target_url", sa.Text(), nullable=False),
            sa.Column("title", sa.String(128), nullable=True),
            sa.Column("utm_source", sa.String(64), nullable=True),
            sa.Column("utm_medium", sa.String(64), nullable=True),
            sa.Column("utm_campaign", sa.String(64), nullable=True),
            sa.Column("click_count", sa.Integer(), server_default="0"),
            sa.Column("is_active", sa.Boolean(), server_default="true"),
            sa.Column("created_by", UUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_short_links_code", "short_links", ["code"])

    # ── link_clicks ──
    if "link_clicks" not in existing_tables:
        op.create_table(
            "link_clicks",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("link_id", UUID(), sa.ForeignKey("short_links.id", ondelete="CASCADE")),
            sa.Column("ip_hash", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("referer", sa.Text(), nullable=True),
            sa.Column("country_code", sa.String(4), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_link_clicks_link_created", "link_clicks", ["link_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_link_clicks_link_created", table_name="link_clicks")
    op.drop_table("link_clicks")
    op.drop_index("ix_short_links_code", table_name="short_links")
    op.drop_table("short_links")
    op.drop_index("ix_partners_follow_up", table_name="partners")
    op.drop_index("ix_partners_status", table_name="partners")
    op.drop_table("partners")
    op.drop_index("uq_weekly_kpi_week", table_name="weekly_kpi_snapshots")
    op.drop_table("weekly_kpi_snapshots")
