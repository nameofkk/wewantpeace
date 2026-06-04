"""Add translation fields to posts and comments

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS title_en VARCHAR(400)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_en TEXT")
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS content_en TEXT")


def downgrade() -> None:
    op.drop_column("comments", "content_en")
    op.drop_column("posts", "content_en")
    op.drop_column("posts", "title_en")
