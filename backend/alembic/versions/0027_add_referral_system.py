"""add referral system columns and rewards table

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── users 테이블 컬럼 추가 ──
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "referral_code" not in user_cols:
        op.add_column("users", sa.Column("referral_code", sa.String(12), nullable=True))
        op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])

    if "referred_by_code" not in user_cols:
        op.add_column("users", sa.Column("referred_by_code", sa.String(12), nullable=True))

    if "referral_pro_expires_at" not in user_cols:
        op.add_column("users", sa.Column("referral_pro_expires_at", sa.DateTime(timezone=True), nullable=True))

    # ── referral_rewards 테이블 ──
    if "referral_rewards" not in existing_tables:
        op.create_table(
            "referral_rewards",
            sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("referrer_id", UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("referee_id", UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(12), nullable=False),
            sa.Column("reward_type", sa.String(32), nullable=False, server_default="pro_7d"),
            sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("referee_activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_referral_rewards_referrer", "referral_rewards", ["referrer_id"])
        op.create_index("ix_referral_rewards_referee", "referral_rewards", ["referee_id"])


def downgrade() -> None:
    op.drop_index("ix_referral_rewards_referee", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referrer", table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_pro_expires_at")
    op.drop_column("users", "referred_by_code")
    op.drop_column("users", "referral_code")
