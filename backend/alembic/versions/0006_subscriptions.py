"""subscriptions and payment_history

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan', sa.String(16), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('billing_key', sa.String(200), nullable=True),
        sa.Column('customer_key', sa.String(64), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False, server_default='4900'),
        sa.Column('currency', sa.String(4), nullable=False, server_default='KRW'),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('next_billing_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('active','cancelled','expired','trial')", name='ck_subscriptions_status'),
        sa.CheckConstraint("plan IN ('pro','pro_plus')", name='ck_subscriptions_plan'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])

    op.create_table(
        'payment_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(4), nullable=False, server_default='KRW'),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('pg_transaction_id', sa.String(200), nullable=True),
        sa.Column('pg_response', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('success','failed','refunded')", name='ck_payment_status'),
    )
    op.create_index('ix_payment_history_user_id', 'payment_history', ['user_id'])


def downgrade() -> None:
    op.drop_table('payment_history')
    op.drop_table('subscriptions')
