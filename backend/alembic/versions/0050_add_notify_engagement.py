"""user_preferences에 notify_engagement 컬럼 추가

24시간 미접속 유저에게 일일 브리핑 푸시 발송 여부 (기본 ON).

Revision ID: 0050
Revises: 0049
"""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("notify_engagement", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "notify_engagement")
