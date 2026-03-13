"""subscriptions 테이블: ls_* 필드 제거, dodo_* 필드 추가

LemonSqueezy → DodoPayments 결제 통합 전환.

Revision ID: 0044
Revises: 0043
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"


def upgrade():
    # LemonSqueezy 필드 제거
    op.drop_column("subscriptions", "ls_subscription_id")
    op.drop_column("subscriptions", "ls_customer_id")
    op.drop_column("subscriptions", "ls_variant_id")

    # DodoPayments 필드 추가
    op.add_column("subscriptions", sa.Column("dodo_subscription_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("dodo_customer_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("dodo_product_id", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("subscriptions", "dodo_subscription_id")
    op.drop_column("subscriptions", "dodo_customer_id")
    op.drop_column("subscriptions", "dodo_product_id")

    op.add_column("subscriptions", sa.Column("ls_subscription_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("ls_customer_id", sa.String(64), nullable=True))
    op.add_column("subscriptions", sa.Column("ls_variant_id", sa.String(64), nullable=True))
