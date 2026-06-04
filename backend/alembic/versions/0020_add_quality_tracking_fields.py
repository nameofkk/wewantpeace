"""Add translation_status and geo_method fields to normalized_events

Revision ID: 0020
Revises: 0019
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('normalized_events', sa.Column('translation_status', sa.String(16), nullable=True))
    op.add_column('normalized_events', sa.Column('geo_method', sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column('normalized_events', 'geo_method')
    op.drop_column('normalized_events', 'translation_status')
