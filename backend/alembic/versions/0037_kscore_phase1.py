"""KScore Phase 1: home_country + raw_score

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-08
"""
from alembic import op

revision = "0037"
down_revision = "0036"


def upgrade() -> None:
    # 1) users 테이블에 home_country 컬럼 추가
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS home_country VARCHAR(4) NOT NULL DEFAULT 'KR'"
    )
    # 2) trending_keywords에 raw_score 컬럼 추가
    op.execute(
        "ALTER TABLE trending_keywords "
        "ADD COLUMN IF NOT EXISTS raw_score FLOAT DEFAULT 0.0"
    )
    # 3) user_preferences에 home_country 컬럼 추가
    op.execute(
        "ALTER TABLE user_preferences "
        "ADD COLUMN IF NOT EXISTS home_country VARCHAR(4) NOT NULL DEFAULT 'KR'"
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "home_country")
    op.drop_column("trending_keywords", "raw_score")
    op.drop_column("users", "home_country")
