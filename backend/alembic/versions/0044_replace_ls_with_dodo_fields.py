"""subscriptions 테이블: ls_* 필드 제거, dodo_* 필드 추가

LemonSqueezy → DodoPayments 결제 통합 전환.

Revision ID: 0044
Revises: 0043
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0044"
down_revision = "0043"


def upgrade():
    conn = op.get_bind()
    # LemonSqueezy 필드 제거 (IF EXISTS)
    for col in ("ls_subscription_id", "ls_customer_id", "ls_variant_id"):
        conn.execute(text(f"ALTER TABLE subscriptions DROP COLUMN IF EXISTS {col}"))

    # DodoPayments 필드 추가 (IF NOT EXISTS)
    for col in ("dodo_subscription_id", "dodo_customer_id", "dodo_product_id"):
        conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS {col} VARCHAR(64)"))


def downgrade():
    conn = op.get_bind()
    for col in ("dodo_subscription_id", "dodo_customer_id", "dodo_product_id"):
        conn.execute(text(f"ALTER TABLE subscriptions DROP COLUMN IF EXISTS {col}"))

    for col in ("ls_subscription_id", "ls_customer_id", "ls_variant_id"):
        conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS {col} VARCHAR(64)"))
