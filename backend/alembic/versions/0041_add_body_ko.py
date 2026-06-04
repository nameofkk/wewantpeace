"""normalized_events에 body_ko 컬럼 추가

한국어 본문을 별도 저장하여 프론트에서 언어별 분기 표시.

Revision ID: 0041
Revises: 0040
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"


def upgrade():
    op.add_column("normalized_events", sa.Column("body_ko", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("normalized_events", "body_ko")
