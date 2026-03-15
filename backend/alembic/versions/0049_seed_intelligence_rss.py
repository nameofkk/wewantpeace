"""Intelligence RSS 피드 시드 데이터

학술/군사/분석 전문 RSS 피드 9개 추가.
rss_collector가 자동으로 수집 시작.

Revision ID: 0049
Revises: 0048
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "0049"
down_revision = "0048"

# 추가할 RSS 피드 목록
_FEEDS = [
    ("SIPRI", "https://www.sipri.org/rss", "A", "global"),
    ("NK News", "https://www.nknews.org/feed/", "B", "KP"),
    ("ISW", "https://www.iswresearch.org/feeds/posts/default", "A", "UA"),
    ("Breaking Defense", "https://breakingdefense.com/feed/", "B", "global"),
    ("Defense One", "https://www.defenseone.com/rss/", "B", "global"),
    ("The War Zone", "https://www.thedrive.com/the-war-zone/feed", "B", "global"),
    ("Haaretz", "https://www.haaretz.com/cmlink/1.628765", "B", "IL"),
    ("NATO", "https://www.nato.int/cps/en/natohq/news.xml", "A", "EU"),
    ("Military Times", "https://www.militarytimes.com/arc/outboundfeeds/rss/", "B", "US"),
]


def upgrade():
    # source_channels 테이블에 INSERT
    conn = op.get_bind()
    now = datetime.now(timezone.utc).isoformat()
    for name, url, tier, geo in _FEEDS:
        # 중복 방지: feed_url이 이미 있으면 스킵
        existing = conn.execute(
            sa.text("SELECT id FROM source_channels WHERE feed_url = :url"),
            {"url": url},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO source_channels (channel_name, source_type, feed_url, source_tier, is_active, created_at) "
                "VALUES (:name, 'rss', :url, :tier, true, :now)"
            ),
            {"name": name, "url": url, "tier": tier, "now": now},
        )


def downgrade():
    conn = op.get_bind()
    urls = [url for _, url, _, _ in _FEEDS]
    for url in urls:
        conn.execute(
            sa.text("DELETE FROM source_channels WHERE feed_url = :url"),
            {"url": url},
        )
