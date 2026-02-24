"""seed rss channels

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RSS_CHANNELS = [
    # Tier A
    {
        "display_name": "Reuters World News",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.92,
        "language": "en",
        "feed_url": "https://feeds.reuters.com/reuters/topNews",
        "topics": ["conflict", "diplomacy", "sanctions"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "BBC World News",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.90,
        "language": "en",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "topics": ["conflict", "diplomacy", "coup", "protest"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Al Jazeera English",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.88,
        "language": "en",
        "feed_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "topics": ["conflict", "diplomacy", "protest"],
        "geo_focus": ["ME", "AF", "AS"],
    },
    {
        "display_name": "AP News International",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.92,
        "language": "en",
        "feed_url": "https://rsshub.app/apnews/topics/apf-intlnews",
        "topics": ["conflict", "diplomacy", "sanctions", "coup"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Deutsche Welle World",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.87,
        "language": "en",
        "feed_url": "https://rss.dw.com/xml/rss-en-world",
        "topics": ["conflict", "diplomacy", "sanctions"],
        "geo_focus": ["EU", "ME", "AS"],
    },
    {
        "display_name": "The Guardian World",
        "source_type": "rss",
        "tier": "A",
        "base_confidence": 0.86,
        "language": "en",
        "feed_url": "https://www.theguardian.com/world/rss",
        "topics": ["conflict", "protest", "diplomacy", "coup"],
        "geo_focus": ["global"],
    },
    # Tier B
    {
        "display_name": "Kyiv Independent",
        "source_type": "rss",
        "tier": "B",
        "base_confidence": 0.80,
        "language": "en",
        "feed_url": "https://kyivindependent.com/feed",
        "topics": ["conflict"],
        "geo_focus": ["UA", "RU", "EU"],
    },
    {
        "display_name": "Radio Free Asia",
        "source_type": "rss",
        "tier": "B",
        "base_confidence": 0.78,
        "language": "en",
        "feed_url": "https://www.rfa.org/english/RSS",
        "topics": ["conflict", "coup", "protest"],
        "geo_focus": ["AS", "KP", "MM", "CN"],
    },
    {
        "display_name": "Middle East Eye",
        "source_type": "rss",
        "tier": "B",
        "base_confidence": 0.78,
        "language": "en",
        "feed_url": "https://www.middleeasteye.net/rss",
        "topics": ["conflict", "diplomacy", "protest"],
        "geo_focus": ["ME", "PS", "IL", "IR", "SY", "YE"],
    },
    {
        "display_name": "NHK World News",
        "source_type": "rss",
        "tier": "B",
        "base_confidence": 0.85,
        "language": "en",
        "feed_url": "https://www3.nhk.or.jp/rss/news/cat6.xml",
        "topics": ["conflict", "diplomacy", "maritime"],
        "geo_focus": ["AS", "KP", "TW", "JP", "KR"],
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(sa.text("SELECT COUNT(*) FROM source_channels WHERE source_type = 'rss'"))
    count = result.scalar()
    if count and count > 0:
        return

    for ch in RSS_CHANNELS:
        conn.execute(
            sa.text("""
                INSERT INTO source_channels
                  (display_name, source_type, tier, base_confidence, language,
                   feed_url, topics, geo_focus, is_active)
                VALUES
                  (:display_name, :source_type, :tier, :base_confidence, :language,
                   :feed_url, :topics, :geo_focus, true)
                ON CONFLICT DO NOTHING
            """).bindparams(
                sa.bindparam("topics", type_=sa.ARRAY(sa.Text())),
                sa.bindparam("geo_focus", type_=sa.ARRAY(sa.Text())),
            ),
            {
                "display_name": ch["display_name"],
                "source_type": ch["source_type"],
                "tier": ch["tier"],
                "base_confidence": ch["base_confidence"],
                "language": ch["language"],
                "feed_url": ch["feed_url"],
                "topics": ch["topics"],
                "geo_focus": ch["geo_focus"],
            },
        )


def downgrade() -> None:
    op.execute("DELETE FROM source_channels WHERE source_type = 'rss'")
