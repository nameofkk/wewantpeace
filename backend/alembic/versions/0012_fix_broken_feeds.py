"""fix broken rss feeds

Revision ID: 0012
Revises: 0011
Create Date: 2026-02-25

수집 실패 피드 5개 수정:
- Reuters World News     → Sky News World (feeds.reuters.com DNS 오류)
- AP News International  → CBS News World (rsshub.app XML 불안정)
- Kyiv Independent       → trailing slash 수정
- Radio Free Europe      → 비활성화 (XML 파싱 오류)
- OCCRP                  → 비활성화 (XML syntax error)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIXES = [
    # Reuters: feeds.reuters.com DNS 불가 → Sky News World
    {
        "old_url": "https://feeds.reuters.com/reuters/topNews",
        "new_display_name": "Sky News World",
        "new_url": "https://feeds.skynews.com/feeds/rss/world.xml",
        "is_active": True,
    },
    # AP News: rsshub.app XML syntax error → CBS News World
    {
        "old_url": "https://rsshub.app/apnews/topics/apf-intlnews",
        "new_display_name": "CBS News World",
        "new_url": "https://www.cbsnews.com/latest/rss/world",
        "is_active": True,
    },
    # Kyiv Independent: invalid XML → trailing slash
    {
        "old_url": "https://kyivindependent.com/feed",
        "new_display_name": "Kyiv Independent",
        "new_url": "https://kyivindependent.com/feed/",
        "is_active": True,
    },
    # RFE-RL: XML 파싱 오류 → 비활성화
    {
        "old_url": "https://www.rferl.org/api/zrqsuvqpiq/rss.html",
        "new_display_name": "Radio Free Europe / RFE-RL",
        "new_url": "https://www.rferl.org/api/zrqsuvqpiq/rss.html",
        "is_active": False,
    },
    # OCCRP: XML syntax error → 비활성화
    {
        "old_url": "https://www.occrp.org/en/rss",
        "new_display_name": "OCCRP",
        "new_url": "https://www.occrp.org/en/rss",
        "is_active": False,
    },
]

_ROLLBACK = {fix["new_url"]: fix["old_url"] for fix in _FIXES}
_ORIGINAL_NAMES = {
    "https://feeds.reuters.com/reuters/topNews": "Reuters World News",
    "https://rsshub.app/apnews/topics/apf-intlnews": "AP News International",
}


def upgrade() -> None:
    conn = op.get_bind()
    for fix in _FIXES:
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


def downgrade() -> None:
    conn = op.get_bind()
    for fix in _FIXES:
        original_name = _ORIGINAL_NAMES.get(fix["old_url"], fix["new_display_name"])
        conn.execute(
            sa.text("""
                UPDATE source_channels
                SET display_name = :display_name,
                    feed_url     = :old_url,
                    is_active    = true
                WHERE feed_url = :new_url
            """),
            {
                "display_name": original_name,
                "old_url": fix["old_url"],
                "new_url": fix["new_url"],
            },
        )
