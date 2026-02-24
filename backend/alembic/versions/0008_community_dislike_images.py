"""community: add dislike_count and images to posts

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('dislike_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('posts', sa.Column('images', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('posts', 'images')
    op.drop_column('posts', 'dislike_count')
