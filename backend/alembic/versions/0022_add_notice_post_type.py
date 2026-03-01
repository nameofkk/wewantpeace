"""add notice post_type and is_pinned column

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) DROP existing CHECK constraint, recreate with 'notice' added
    op.drop_constraint("ck_posts_type", "posts", type_="check")
    op.create_check_constraint(
        "ck_posts_type",
        "posts",
        "post_type IN ('discussion','question','analysis','notice')",
    )

    # 2) Add is_pinned column
    op.add_column("posts", sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("posts", "is_pinned")
    op.drop_constraint("ck_posts_type", "posts", type_="check")
    op.create_check_constraint(
        "ck_posts_type",
        "posts",
        "post_type IN ('discussion','question','analysis')",
    )
