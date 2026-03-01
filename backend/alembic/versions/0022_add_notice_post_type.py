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
    conn = op.get_bind()

    # 1) CHECK 제약 교체 (이미 적용돼 있으면 DROP 후 재생성)
    conn.execute(sa.text("ALTER TABLE posts DROP CONSTRAINT IF EXISTS ck_posts_type"))
    conn.execute(sa.text(
        "ALTER TABLE posts ADD CONSTRAINT ck_posts_type "
        "CHECK (post_type IN ('discussion','question','analysis','notice'))"
    ))

    # 2) is_pinned 컬럼 (이미 있으면 무시)
    conn.execute(sa.text(
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE"
    ))


def downgrade() -> None:
    op.drop_column("posts", "is_pinned")
    op.drop_constraint("ck_posts_type", "posts", type_="check")
    op.create_check_constraint(
        "ck_posts_type",
        "posts",
        "post_type IN ('discussion','question','analysis')",
    )
