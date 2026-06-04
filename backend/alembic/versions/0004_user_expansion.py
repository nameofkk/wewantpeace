"""user expansion: nickname, status, role, profile, bio, consents

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users 테이블 컬럼 추가
    op.add_column('users', sa.Column('nickname', sa.String(30), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('profile_image_url', sa.String(512), nullable=True))
    op.add_column('users', sa.Column('birth_year', sa.SmallInteger(), nullable=True))
    op.add_column('users', sa.Column('status', sa.String(16), nullable=False, server_default='active'))
    op.add_column('users', sa.Column('role', sa.String(16), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('agreed_terms_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('users', sa.Column('agreed_privacy_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('users', sa.Column('marketing_agreed_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('users', sa.Column('suspended_until', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('users', sa.Column('suspend_reason', sa.String(200), nullable=True))
    
    # 유니크 인덱스
    op.create_unique_constraint('uq_users_nickname', 'users', ['nickname'])
    
    # CHECK 제약
    op.create_check_constraint(
        'ck_users_status',
        'users',
        "status IN ('active', 'suspended', 'deleted')"
    )
    op.create_check_constraint(
        'ck_users_role',
        'users',
        "role IN ('user', 'moderator', 'admin')"
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_role', 'users', type_='check')
    op.drop_constraint('ck_users_status', 'users', type_='check')
    op.drop_constraint('uq_users_nickname', 'users', type_='unique')
    for col in ['suspend_reason', 'suspended_until', 'marketing_agreed_at', 'agreed_privacy_at',
                'agreed_terms_at', 'role', 'status', 'birth_year', 'profile_image_url',
                'bio', 'display_name', 'nickname']:
        op.drop_column('users', col)
