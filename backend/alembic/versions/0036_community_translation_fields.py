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
    op.add_column("posts", sa.Column("title_en", sa.String(400), nullable=True))
    op.add_column("posts", sa.Column("content_en", sa.Text(), nullable=True))
    op.add_column("comments", sa.Column("content_en", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "content_en")
    op.drop_column("posts", "content_en")
    op.drop_column("posts", "title_en")
