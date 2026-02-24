"""fix more broken rss feeds

Revision ID: 0013
Revises: 0012
Create Date: 2026-02-25

0012에서 수정되지 않은 추가 오류 피드 8개 처리:
- VOA News World        → URL 교체 (feeds.voanews.com invalid token)
- Al Jazeera Arabic     → URL 교체 (syntax error)
- Jerusalem Post World  → 비활성화 (HTML not XML, RSS 폐지)
- Iran International    → 비활성화 (junk after document element)
- Kurdistan 24          → 비활성화 (syntax error)
- Libya Observer        → 비활성화 (syntax error)
- Sudan Tribune         → 비활성화 (invalid token)
- Meduza (Russia EN)    → 비활성화 (undefined entity)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# URL 교체 (작동하는 대체 URL 확인된 것만)
_URL_FIXES = [
    # VOA: feeds.voanews.com → voanews.com 직접 RSS
    {
        "old_url": "https://feeds.voanews.com/voaworld/rss",
        "new_display_name": "VOA News World",
        "new_url": "https://www.voanews.com/rss?format=rss",
        "is_active": True,
    },
    # Al Jazeera Arabic: aljazeera.net XML 인코딩 오류 → mubasher 피드
    {
        "old_url": "https://www.aljazeera.net/xml/rss/all.xml",
        "new_display_name": "Al Jazeera Arabic",
        "new_url": "https://www.aljazeera.net/rss",
        "is_active": True,
    },
]

# 비활성화만 (RSS 중단 또는 XML 자체 불량)
_DISABLE_URLS = [
    "https://www.jpost.com/rss/rssfeedsworld.aspx",    # Jerusalem Post: HTML 반환
    "https://www.iranintl.com/en/rss",                 # Iran International: junk after element
    "https://www.kurdistan24.net/en/rss",              # Kurdistan 24: syntax error
    "https://www.libyaobserver.ly/feed",               # Libya Observer: syntax error
    "https://sudantribune.com/feed/",                  # Sudan Tribune: invalid token
    "https://meduza.io/en/rss/all",                    # Meduza: undefined entity
]


def upgrade() -> None:
    conn = op.get_bind()

    # URL 교체
    for fix in _URL_FIXES:
        conn.execute(
            sa.text("""
                UPDATE source_channels
                SET display_name = :display_name,
                    feed_url     = :new_url,
                    is_active    = :is_active
                WHERE feed_url = :old_url
            """),
            {
                "display_name": fix["new_display_name"],
                "new_url": fix["new_url"],
                "is_active": fix["is_active"],
                "old_url": fix["old_url"],
            },
        )

    # 비활성화
    for url in _DISABLE_URLS:
        conn.execute(
            sa.text("UPDATE source_channels SET is_active = false WHERE feed_url = :url"),
            {"url": url},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # URL 롤백
    for fix in _URL_FIXES:
        conn.execute(
            sa.text("""
                UPDATE source_channels
                SET feed_url  = :old_url,
                    is_active = true
                WHERE feed_url = :new_url
            """),
            {"old_url": fix["old_url"], "new_url": fix["new_url"]},
        )

    # 재활성화
    for url in _DISABLE_URLS:
        conn.execute(
            sa.text("UPDATE source_channels SET is_active = true WHERE feed_url = :url"),
            {"url": url},
        )
