"""community: posts, comments, reactions, reports, admin_logs

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # posts
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('post_type', sa.String(16), nullable=False, server_default='discussion'),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("post_type IN ('discussion','question','analysis')", name='ck_posts_type'),
        sa.CheckConstraint("status IN ('active','hidden','deleted')", name='ck_posts_status'),
    )
    op.create_index('ix_posts_user_id', 'posts', ['user_id'])
    op.create_index('ix_posts_cluster_id', 'posts', ['cluster_id'])
    op.create_index('ix_posts_created_at', 'posts', ['created_at'])
    op.create_index('ix_posts_post_type', 'posts', ['post_type'])

    # comments
    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('active','hidden','deleted')", name='ck_comments_status'),
    )
    op.create_index('ix_comments_post_id', 'comments', ['post_id'])
    op.create_index('ix_comments_user_id', 'comments', ['user_id'])
    op.create_index('ix_comments_parent_id', 'comments', ['parent_id'])

    # comment_reactions
    op.create_table(
        'comment_reactions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reaction_type', sa.String(16), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'comment_id', name='uq_comment_reactions'),
        sa.CheckConstraint("reaction_type IN ('like','dislike')", name='ck_comment_reaction_type'),
    )

    # post_reactions
    op.create_table(
        'post_reactions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reaction_type', sa.String(16), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'post_id', name='uq_post_reactions'),
        sa.CheckConstraint("reaction_type IN ('like','dislike')", name='ck_post_reaction_type'),
    )

    # reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_type', sa.String(16), nullable=False),
        sa.Column('target_id', sa.String(64), nullable=False),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.CheckConstraint("target_type IN ('post','comment','user')", name='ck_reports_target_type'),
        sa.CheckConstraint("status IN ('pending','resolved','dismissed')", name='ck_reports_status'),
    )
    op.create_index('ix_reports_status', 'reports', ['status'])

    # admin_logs
    op.create_table(
        'admin_logs',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=True),
        sa.Column('target_id', sa.String(64), nullable=True),
        sa.Column('detail', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_admin_logs_admin_id', 'admin_logs', ['admin_id'])
    op.create_index('ix_admin_logs_created_at', 'admin_logs', ['created_at'])


def downgrade() -> None:
    for tbl in ['admin_logs', 'reports', 'post_reactions', 'comment_reactions', 'comments', 'posts']:
        op.drop_table(tbl)
