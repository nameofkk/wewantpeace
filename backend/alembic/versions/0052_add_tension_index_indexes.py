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
    # ── tension_index 복합 인덱스 ──
    op.create_index(
        "ix_tension_index_country_time",
        "tension_index",
        ["country_code", sa.text("time DESC")],
    )

    # ── subscriptions 인덱스 ──
    op.create_index(
        "ix_subscriptions_user_id",
        "subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_subscriptions_status",
        "subscriptions",
        ["status"],
    )

    # ── normalized_events 인덱스 ──
    op.create_index(
        "ix_normalized_events_event_time",
        "normalized_events",
        ["event_time"],
    )
    op.create_index(
        "ix_normalized_events_country",
        "normalized_events",
        ["country_code"],
    )

    # ── user_areas 인덱스 ──
    op.create_index(
        "ix_user_areas_user_id",
        "user_areas",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_areas_user_id", "user_areas")
    op.drop_index("ix_normalized_events_country", "normalized_events")
    op.drop_index("ix_normalized_events_event_time", "normalized_events")
    op.drop_index("ix_subscriptions_status", "subscriptions")
    op.drop_index("ix_subscriptions_user_id", "subscriptions")
    op.drop_index("ix_tension_index_country_time", "tension_index")
