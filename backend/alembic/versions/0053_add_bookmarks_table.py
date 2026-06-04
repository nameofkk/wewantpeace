"""Add bookmarks table

커뮤니티 게시글 북마크 기능 지원을 위한 bookmarks 테이블 생성.
- user_id + post_id 복합 유니크 제약조건
- CASCADE 삭제

Revision ID: 0053
Revises: 0052
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "post_id", name="uq_bookmark_user_post"),
    )
    # 사용자별 북마크 조회를 위한 인덱스
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])
    # 게시글별 북마크 수 조회를 위한 인덱스
    op.create_index("ix_bookmarks_post_id", "bookmarks", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_bookmarks_post_id", table_name="bookmarks")
    op.drop_index("ix_bookmarks_user_id", table_name="bookmarks")
    op.drop_table("bookmarks")
