"""add billing_interval column to subscriptions

Revision ID: 0057
Revises: 0056
"""
import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"


def upgrade():
    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_interval",
            sa.String(20),
            nullable=False,
            server_default="monthly",
        ),
    )
    op.create_check_constraint(
        "ck_subscriptions_billing_interval",
        "subscriptions",
        "billing_interval IN ('monthly', 'annual', 'lifetime')",
    )
    # amount 기본값 변경: 390 → 699
    op.alter_column(
        "subscriptions",
        "amount",
        server_default="699",
    )


def downgrade():
    op.drop_constraint("ck_subscriptions_billing_interval", "subscriptions")
    op.drop_column("subscriptions", "billing_interval")
    op.alter_column(
        "subscriptions",
        "amount",
        server_default="390",
    )
