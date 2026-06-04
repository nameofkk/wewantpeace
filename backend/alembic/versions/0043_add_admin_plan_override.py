"""users 테이블에 admin_plan_override 컬럼 추가

어드민이 수동 설정한 플랜을 expire_subscriptions 크론이 다운그레이드하지 않도록.

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"


def upgrade():
    op.add_column(
        "users",
        sa.Column("admin_plan_override", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("users", "admin_plan_override")
