"""Add tension_index, subscriptions, normalized_events, user_areas indexes

- tension_index: (country_code, time DESC) 복합 인덱스
- subscriptions: user_id, status 인덱스
- normalized_events: event_time, country_code 인덱스
- user_areas: user_id 인덱스

Revision ID: 0052
Revises: 0051
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tension_index 복합 인덱스 (DESC는 raw SQL 필요) ──
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tension_index_country_time "
        "ON tension_index (country_code, time DESC)"
    )

    # ── subscriptions 인덱스 ──
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id "
        "ON subscriptions (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_status "
        "ON subscriptions (status)"
    )

    # ── normalized_events 인덱스 ──
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_normalized_events_event_time "
        "ON normalized_events (event_time)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_normalized_events_country "
        "ON normalized_events (country_code)"
    )

    # ── user_areas 인덱스 ──
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_areas_user_id "
        "ON user_areas (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_areas_user_id")
    op.execute("DROP INDEX IF EXISTS ix_normalized_events_country")
    op.execute("DROP INDEX IF EXISTS ix_normalized_events_event_time")
    op.execute("DROP INDEX IF EXISTS ix_subscriptions_status")
    op.execute("DROP INDEX IF EXISTS ix_subscriptions_user_id")
    op.execute("DROP INDEX IF EXISTS ix_tension_index_country_time")
