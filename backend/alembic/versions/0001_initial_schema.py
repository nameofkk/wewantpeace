"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source_channels: Telegram 화이트리스트 + RSS 소스
    op.create_table(
        "source_channels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column(
            "tier",
            sa.String(1),
            nullable=False,
            comment="A=공식/주요언론, B=검증된OSINT, C=일반OSINT, D=미검증",
        ),
        sa.Column("base_confidence", sa.Float(), nullable=False, server_default="0.70"),
        sa.Column("language", sa.String(8), nullable=True, server_default="en"),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "geo_focus",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="telegram"),
        sa.Column("feed_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("tier IN ('A','B','C','D')", name="ck_source_channels_tier"),
        sa.UniqueConstraint("channel_id", name="uq_source_channels_channel_id"),
    )

    # raw_events: 원본 수집 데이터
    op.create_table(
        "raw_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_channel_id",
            sa.Integer(),
            sa.ForeignKey("source_channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("lang", sa.String(8), nullable=True),
        sa.Column(
            "collected_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("source_type", "external_id", name="uq_raw_events_source_external"),
    )
    op.create_index("idx_raw_events_processed", "raw_events", ["processed", "collected_at"])
    op.create_index("idx_raw_events_source_type", "raw_events", ["source_type", "collected_at"])

    # normalized_events: 정규화된 이벤트
    op.create_table(
        "normalized_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "raw_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(32), nullable=False),
        sa.Column("entity_anchor", sa.String(256), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("geohash5", sa.String(8), nullable=True),
        sa.Column("country_code", sa.String(4), nullable=True),
        sa.Column("severity", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("source_tier", sa.String(1), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("event_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_ne_geohash_topic", "normalized_events", ["geohash5", "topic", "event_time"])
    op.create_index("idx_ne_dedup", "normalized_events", ["dedup_key"])
    op.create_index("idx_ne_country", "normalized_events", ["country_code", "event_time"])

    # issue_clusters: 클러스터링된 이슈
    op.create_table(
        "issue_clusters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("cluster_key", sa.String(512), nullable=False),
        sa.Column("geohash5", sa.String(8), nullable=False),
        sa.Column("topic", sa.String(32), nullable=False),
        sa.Column("entity_anchor", sa.String(256), nullable=True),
        sa.Column("country_code", sa.String(4), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("severity", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("kscore", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_spike", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("spike_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "source_tiers",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("independent_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_event_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_event_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_cluster_geo", "issue_clusters", ["geohash5", "last_event_at"])
    op.create_index("idx_cluster_spike", "issue_clusters", ["is_spike", "spike_at"])
    op.create_index("idx_cluster_country", "issue_clusters", ["country_code", "last_event_at"])

    # cluster_events: 클러스터 ↔ 이벤트 연결
    op.create_table(
        "cluster_events",
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("normalized_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # tension_index: 긴장도 지수 (TimescaleDB 하이퍼테이블)
    op.create_table(
        "tension_index",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False, primary_key=True),
        sa.Column("country_code", sa.String(4), nullable=False, primary_key=True),
        sa.Column("region_code", sa.String(16), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tension_level", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("event_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("accel_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("spillover_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("percentile_30d", sa.Float(), nullable=True, server_default="0.0"),
    )
    op.create_index("idx_ti_country", "tension_index", ["country_code", "time"])

    # TimescaleDB 하이퍼테이블 생성 (TimescaleDB 없으면 skip — Supabase 등 표준 PG 호환)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('tension_index', 'time', if_not_exists => TRUE);
            END IF;
        END$$
    """)

    # trending_keywords
    op.create_table(
        "trending_keywords",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("keyword", sa.String(256), nullable=False),
        sa.Column("normalized_kw", sa.String(256), nullable=False),
        sa.Column("kscore", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("topic", sa.String(32), nullable=True),
        sa.Column(
            "country_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "cluster_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("scope", sa.String(64), nullable=False, server_default="global"),
        sa.Column(
            "calculated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_kw_scope_score",
        "trending_keywords",
        ["scope", sa.text("kscore DESC"), "calculated_at"],
    )

    # users
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("firebase_uid", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("plan", sa.String(16), nullable=False, server_default="free"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_active",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("plan IN ('free','pro','pro_plus')", name="ck_users_plan"),
    )

    # user_areas
    op.create_table(
        "user_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("area_type", sa.String(16), nullable=False, server_default="country"),
        sa.Column("country_code", sa.String(4), nullable=True),
        sa.Column("geojson", postgresql.JSONB(), nullable=True),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("notify_verified", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_fast", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "area_type IN ('country','polygon','radius')", name="ck_user_areas_type"
        ),
    )
    op.create_index("idx_user_areas_user", "user_areas", ["user_id"])

    # user_push_tokens
    op.create_table(
        "user_push_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fcm_token", sa.String(512), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False, server_default="web"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_used",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "fcm_token", name="uq_user_push_tokens"),
    )

    # user_preferences
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("language", sa.String(8), nullable=False, server_default="ko"),
        sa.Column("min_severity", sa.SmallInteger(), nullable=False, server_default="35"),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{conflict,terror,coup,sanctions,cyber,protest}'"),
        ),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Seoul"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("user_push_tokens")
    op.drop_table("user_areas")
    op.drop_table("users")
    op.drop_table("trending_keywords")
    op.drop_table("tension_index")
    op.drop_table("cluster_events")
    op.drop_table("issue_clusters")
    op.drop_table("normalized_events")
    op.drop_table("raw_events")
    op.drop_table("source_channels")
