"""weekly_editions — 주간 브리핑 한 호 (뉴스레터·무료 브리프·Pro+ 리포트·스레드 주간 카드가 같이 읽는다)

Revision ID: 0063
Revises: 0062
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0063"
down_revision = "0062"


def upgrade() -> None:
    op.create_table(
        "weekly_editions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("week_key", sa.String(10), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_ko_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sent_en_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("weekly_editions")
