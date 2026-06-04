"""모든 public 테이블에 RLS(Row Level Security) 활성화

Supabase PostgREST를 통한 무인가 직접 접근 차단.
백엔드(postgres 서비스 롤)는 테이블 소유자이므로 RLS 우회 → 기존 코드 무영향.

Revision ID: 0042
Revises: 0041
"""
from alembic import op

revision = "0042"
down_revision = "0041"

_TABLES = [
    "alert_delivery_log",
    "admin_logs",
    "app_events",
    "cluster_change_logs",
    "cluster_events",
    "comment_reactions",
    "comments",
    "feedbacks",
    "issue_clusters",
    "link_clicks",
    "marketing_email_logs",
    "normalized_events",
    "notifications",
    "partners",
    "payment_history",
    "paywall_events",
    "post_reactions",
    "posts",
    "raw_events",
    "reports",
    "short_links",
    "social_post_platform",
    "social_posts",
    "source_channels",
    "spike_events",
    "subscriptions",
    "tension_index",
    "term_versions",
    "trending_keywords",
    "user_areas",
    "user_consents",
    "user_missed_alert_summary",
    "user_preferences",
    "user_push_tokens",
    "users",
    "weekly_kpi_snapshots",
]


def upgrade():
    for table in _TABLES:
        # SAFE: table names are internal constants, not user input
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade():
    for table in _TABLES:
        # SAFE: table names are internal constants, not user input
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
