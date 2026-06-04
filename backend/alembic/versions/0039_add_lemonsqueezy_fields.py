"""subscriptions 테이블에 LemonSqueezy 필드 추가

Revision ID: 0039
Revises: 0038
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("ls_subscription_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("ls_customer_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("ls_variant_id", sa.String(64), nullable=True),
    )

    # platform CHECK 제약조건은 없으므로 (String 필드) 별도 수정 불필요
    # platform 컬럼 길이 확장 (16 -> 32, 이미 0018에서 16으로 설정됨)
    # subscription.py 모델에서는 String(32)로 선언되어 있으므로 DB도 맞춤
    op.alter_column(
        "subscriptions",
        "platform",
        type_=sa.String(32),
        existing_type=sa.String(16),
    )


def downgrade() -> None:
    op.alter_column(
        "subscriptions",
        "platform",
        type_=sa.String(16),
        existing_type=sa.String(32),
    )
    op.drop_column("subscriptions", "ls_variant_id")
    op.drop_column("subscriptions", "ls_customer_id")
    op.drop_column("subscriptions", "ls_subscription_id")
