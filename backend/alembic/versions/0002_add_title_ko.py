"""add title_ko to issue_clusters

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-23
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issue_clusters",
        sa.Column("title_ko", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("issue_clusters", "title_ko")
