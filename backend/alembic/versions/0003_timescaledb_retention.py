"""TimescaleDB 보존 정책 및 인덱스 추가 (L-6)

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # tension_index: 90일 보존 정책 (TimescaleDB 있을 때만 — Supabase 등 표준 PG 호환)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM add_retention_policy(
                    'tension_index',
                    INTERVAL '90 days',
                    if_not_exists => true
                );
            END IF;
        END$$
    """)

    # raw_events: 30일 보존 (처리 완료된 이벤트 정리)
    # TimescaleDB 하이퍼테이블이 아니므로 일반 DELETE 기반 함수 사용
    # (별도 cron 또는 pg_cron으로 실행 권장)

    # 인덱스 추가 (성능 개선)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_events_collected_at
        ON raw_events (collected_at DESC)
        WHERE processed = false
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_normalized_events_event_time_country
        ON normalized_events (event_time DESC, country_code)
        WHERE is_duplicate = false
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_issue_clusters_last_event_at_severity
        ON issue_clusters (last_event_at DESC, severity)
        WHERE severity >= 30
    """)

    # NormalizedEvent dedup_key 유니크 제약 (H-5 TOCTOU 완화)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_normalized_events_dedup_key_unique
        ON normalized_events (dedup_key)
        WHERE is_duplicate = false
    """)


def downgrade():
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM remove_retention_policy('tension_index', if_not_exists => true);
            END IF;
        END$$
    """)
    op.execute("DROP INDEX IF EXISTS idx_raw_events_collected_at")
    op.execute("DROP INDEX IF EXISTS idx_normalized_events_event_time_country")
    op.execute("DROP INDEX IF EXISTS idx_issue_clusters_last_event_at_severity")
    op.execute("DROP INDEX IF EXISTS idx_normalized_events_dedup_key_unique")
