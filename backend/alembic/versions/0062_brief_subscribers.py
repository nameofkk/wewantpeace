"""brief_subscribers — 로그인 없는 나라별 주간 브리프 구독 (이중 확인)

Revision ID: 0062
Revises: 0061
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"


def upgrade() -> None:
    op.create_table(
        "brief_subscribers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("countries", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("lang", sa.String(4), nullable=False, server_default="en"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("consent_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_brief_subscribers_status", "brief_subscribers", ["status"])


def downgrade() -> None:
    op.drop_index("ix_brief_subscribers_status", table_name="brief_subscribers")
    op.drop_table("brief_subscribers")
