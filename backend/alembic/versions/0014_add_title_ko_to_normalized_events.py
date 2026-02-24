"""add title_ko to normalized_events

Revision ID: 0014
Revises: 0013
Create Date: 2026-02-25

normalized_events 테이블에 title_ko 컬럼 누락 → process_raw_event UndefinedColumnError 수정
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "normalized_events",
        sa.Column("title_ko", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("normalized_events", "title_ko")
