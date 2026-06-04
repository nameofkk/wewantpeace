"""Add store IAP support columns to subscriptions and payment_history

Revision ID: 0018
Revises: 0017
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # subscriptions 테이블에 스토어 IAP 컬럼 추가
    op.add_column('subscriptions', sa.Column('platform', sa.String(16), nullable=False, server_default='web'))
    op.add_column('subscriptions', sa.Column('store_product_id', sa.String(128), nullable=True))
    op.add_column('subscriptions', sa.Column('store_transaction_id', sa.String(256), nullable=True))
    op.add_column('subscriptions', sa.Column('store_original_transaction_id', sa.String(256), nullable=True))
    op.add_column('subscriptions', sa.Column('auto_renewing', sa.Boolean(), nullable=False, server_default='true'))

    # status CHECK 제약조건 교체 (grace_period, billing_retry 추가)
    op.drop_constraint('ck_subscriptions_status', 'subscriptions', type_='check')
    op.create_check_constraint(
        'ck_subscriptions_status', 'subscriptions',
        "status IN ('active','cancelled','expired','trial','grace_period','billing_retry')"
    )

    # payment_history에 platform 추가
    op.add_column('payment_history', sa.Column('platform', sa.String(16), nullable=False, server_default='web'))


def downgrade() -> None:
    op.drop_column('payment_history', 'platform')

    op.drop_constraint('ck_subscriptions_status', 'subscriptions', type_='check')
    op.create_check_constraint(
        'ck_subscriptions_status', 'subscriptions',
        "status IN ('active','cancelled','expired','trial')"
    )

    op.drop_column('subscriptions', 'auto_renewing')
    op.drop_column('subscriptions', 'store_original_transaction_id')
    op.drop_column('subscriptions', 'store_transaction_id')
    op.drop_column('subscriptions', 'store_product_id')
    op.drop_column('subscriptions', 'platform')
