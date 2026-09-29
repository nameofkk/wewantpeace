"""social_posts.reply_text — Threads 게시 직후 다는 출처 댓글

영어 브리프 개편(2026-09-30)으로 댓글이 고정 홍보 문구에서 "이 브리프의 출처 목록"으로
바뀌었다. 출처는 생성 시점에 DB 에서 모으는데 발행 어댑터는 DB 를 보지 않으므로 같이 저장한다.

Revision ID: 0061
Revises: 0060
"""
import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"


def upgrade() -> None:
    op.add_column("social_posts", sa.Column("reply_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("social_posts", "reply_text")
