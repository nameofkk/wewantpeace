"""Add composite index on trending_keywords for push notification dedup

Revision ID: 0019
Revises: 0018
Create Date: 2026-02-26
"""
from alembic import op

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_trending_kw_scope_nkw_calcat',
        'trending_keywords',
        ['scope', 'normalized_kw', 'calculated_at'],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_trending_kw_scope_nkw_calcat', table_name='trending_keywords')
