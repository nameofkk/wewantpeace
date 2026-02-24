"""seed more rss channels

Revision ID: 0011
Revises: 0010
Create Date: 2026-02-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MORE_RSS_CHANNELS = [
    # ── Tier A 추가 ──────────────────────────────────────────────────────────
    {
        "display_name": "France 24 English",
        "source_type": "rss", "tier": "A", "base_confidence": 0.87, "language": "en",
        "feed_url": "https://www.france24.com/en/rss",
        "topics": ["conflict", "diplomacy", "coup", "protest"],
        "geo_focus": ["global", "AF", "ME", "EU"],
    },
    {
        "display_name": "VOA News World",
        "source_type": "rss", "tier": "A", "base_confidence": 0.85, "language": "en",
        "feed_url": "https://feeds.voanews.com/voaworld/rss",
        "topics": ["conflict", "sanctions", "coup", "diplomacy"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "NYT World News",
        "source_type": "rss", "tier": "A", "base_confidence": 0.88, "language": "en",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "topics": ["conflict", "diplomacy", "sanctions", "coup"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Washington Post World",
        "source_type": "rss", "tier": "A", "base_confidence": 0.87, "language": "en",
        "feed_url": "https://feeds.washingtonpost.com/rss/world",
        "topics": ["conflict", "diplomacy", "sanctions"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "UN News",
        "source_type": "rss", "tier": "A", "base_confidence": 0.90, "language": "en",
        "feed_url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "topics": ["conflict", "diplomacy", "humanitarian"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "TASS English",
        "source_type": "rss", "tier": "A", "base_confidence": 0.60, "language": "en",
        "feed_url": "https://tass.com/rss/v2.xml",
        "topics": ["conflict", "diplomacy", "sanctions"],
        "geo_focus": ["RU", "UA", "EU", "AS"],
    },
    {
        "display_name": "BBC Arabic",
        "source_type": "rss", "tier": "A", "base_confidence": 0.88, "language": "ar",
        "feed_url": "https://feeds.bbci.co.uk/arabic/rss.xml",
        "topics": ["conflict", "diplomacy", "coup", "protest"],
        "geo_focus": ["ME", "AF", "AR"],
    },
    {
        "display_name": "DW Arabic",
        "source_type": "rss", "tier": "A", "base_confidence": 0.85, "language": "ar",
        "feed_url": "https://rss.dw.com/xml/rss-ar-all",
        "topics": ["conflict", "diplomacy", "protest"],
        "geo_focus": ["ME", "AF", "AR"],
    },
    {
        "display_name": "Al Jazeera Arabic",
        "source_type": "rss", "tier": "A", "base_confidence": 0.86, "language": "ar",
        "feed_url": "https://www.aljazeera.net/xml/rss/all.xml",
        "topics": ["conflict", "diplomacy", "protest"],
        "geo_focus": ["ME", "AF", "AR"],
    },
    # ── Tier B 추가 ──────────────────────────────────────────────────────────
    {
        "display_name": "Radio Free Europe / RFE-RL",
        "source_type": "rss", "tier": "B", "base_confidence": 0.82, "language": "en",
        "feed_url": "https://www.rferl.org/api/zrqsuvqpiq/rss.html",
        "topics": ["conflict", "coup", "protest", "sanctions"],
        "geo_focus": ["RU", "UA", "BY", "KZ", "GE", "AM", "AZ", "EU"],
    },
    {
        "display_name": "Foreign Policy",
        "source_type": "rss", "tier": "B", "base_confidence": 0.83, "language": "en",
        "feed_url": "https://foreignpolicy.com/feed/",
        "topics": ["conflict", "diplomacy", "sanctions", "maritime"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "The Diplomat",
        "source_type": "rss", "tier": "B", "base_confidence": 0.82, "language": "en",
        "feed_url": "https://thediplomat.com/feed/",
        "topics": ["conflict", "diplomacy", "maritime", "coup"],
        "geo_focus": ["AS", "KP", "TW", "CN", "JP", "KR", "IN", "PK"],
    },
    {
        "display_name": "War on the Rocks",
        "source_type": "rss", "tier": "B", "base_confidence": 0.80, "language": "en",
        "feed_url": "https://warontherocks.com/feed/",
        "topics": ["conflict", "sanctions", "cyber", "maritime"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Bellingcat",
        "source_type": "rss", "tier": "B", "base_confidence": 0.85, "language": "en",
        "feed_url": "https://www.bellingcat.com/feed/",
        "topics": ["conflict", "sanctions", "cyber"],
        "geo_focus": ["global", "RU", "UA", "SY", "ME"],
    },
    {
        "display_name": "OCCRP",
        "source_type": "rss", "tier": "B", "base_confidence": 0.83, "language": "en",
        "feed_url": "https://www.occrp.org/en/rss",
        "topics": ["sanctions", "coup", "protest"],
        "geo_focus": ["global", "EU", "RU", "ME", "AF"],
    },
    {
        "display_name": "Defense News",
        "source_type": "rss", "tier": "B", "base_confidence": 0.80, "language": "en",
        "feed_url": "https://www.defensenews.com/arc/outboundfeeds/rss/",
        "topics": ["conflict", "sanctions", "maritime", "cyber"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "South China Morning Post World",
        "source_type": "rss", "tier": "B", "base_confidence": 0.78, "language": "en",
        "feed_url": "https://www.scmp.com/rss/4/feed",
        "topics": ["conflict", "diplomacy", "maritime", "coup"],
        "geo_focus": ["AS", "CN", "TW", "KP", "HK"],
    },
    {
        "display_name": "The Straits Times World",
        "source_type": "rss", "tier": "B", "base_confidence": 0.80, "language": "en",
        "feed_url": "https://www.straitstimes.com/news/world/rss.xml",
        "topics": ["conflict", "diplomacy", "maritime", "coup"],
        "geo_focus": ["AS", "SG", "MY", "TH", "PH", "ID", "MM"],
    },
    {
        "display_name": "Yonhap News English",
        "source_type": "rss", "tier": "B", "base_confidence": 0.82, "language": "en",
        "feed_url": "https://en.yna.co.kr/RSS/news.xml",
        "topics": ["conflict", "diplomacy", "sanctions"],
        "geo_focus": ["KP", "KR", "JP", "CN", "AS"],
    },
    {
        "display_name": "Dawn (Pakistan)",
        "source_type": "rss", "tier": "B", "base_confidence": 0.78, "language": "en",
        "feed_url": "https://www.dawn.com/feeds/home",
        "topics": ["conflict", "diplomacy", "terror"],
        "geo_focus": ["PK", "IN", "AF", "AS"],
    },
    {
        "display_name": "Times of India International",
        "source_type": "rss", "tier": "B", "base_confidence": 0.76, "language": "en",
        "feed_url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "topics": ["conflict", "diplomacy", "terror"],
        "geo_focus": ["IN", "PK", "CN", "AS"],
    },
    {
        "display_name": "Jerusalem Post World",
        "source_type": "rss", "tier": "B", "base_confidence": 0.76, "language": "en",
        "feed_url": "https://www.jpost.com/rss/rssfeedsworld.aspx",
        "topics": ["conflict", "diplomacy", "terror", "sanctions"],
        "geo_focus": ["ME", "IL", "PS", "IR", "SY", "LB"],
    },
    {
        "display_name": "Iran International",
        "source_type": "rss", "tier": "B", "base_confidence": 0.76, "language": "en",
        "feed_url": "https://www.iranintl.com/en/rss",
        "topics": ["conflict", "protest", "sanctions", "diplomacy"],
        "geo_focus": ["IR", "ME", "IQ", "SY"],
    },
    {
        "display_name": "Kurdistan 24",
        "source_type": "rss", "tier": "B", "base_confidence": 0.74, "language": "en",
        "feed_url": "https://www.kurdistan24.net/en/rss",
        "topics": ["conflict", "diplomacy", "terror"],
        "geo_focus": ["IQ", "SY", "TR", "IR", "ME"],
    },
    # ── Tier C ────────────────────────────────────────────────────────────────
    {
        "display_name": "ICG (Crisis Group)",
        "source_type": "rss", "tier": "C", "base_confidence": 0.88, "language": "en",
        "feed_url": "https://www.crisisgroup.org/rss.xml",
        "topics": ["conflict", "coup", "diplomacy"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Global Voices",
        "source_type": "rss", "tier": "C", "base_confidence": 0.72, "language": "en",
        "feed_url": "https://globalvoices.org/feed/",
        "topics": ["protest", "coup", "conflict"],
        "geo_focus": ["global"],
    },
    {
        "display_name": "Daily Sabah (Turkey)",
        "source_type": "rss", "tier": "C", "base_confidence": 0.65, "language": "en",
        "feed_url": "https://www.dailysabah.com/rssFeed/push_notifications",
        "topics": ["conflict", "diplomacy", "terror"],
        "geo_focus": ["TR", "ME", "SY", "IQ", "EU"],
    },
    {
        "display_name": "Libya Observer",
        "source_type": "rss", "tier": "C", "base_confidence": 0.68, "language": "en",
        "feed_url": "https://www.libyaobserver.ly/feed",
        "topics": ["conflict", "coup", "diplomacy"],
        "geo_focus": ["LY", "AF", "ME"],
    },
    {
        "display_name": "Sudan Tribune",
        "source_type": "rss", "tier": "C", "base_confidence": 0.70, "language": "en",
        "feed_url": "https://sudantribune.com/feed/",
        "topics": ["conflict", "coup", "diplomacy", "humanitarian"],
        "geo_focus": ["SD", "SS", "AF"],
    },
    {
        "display_name": "Ethiopia Insight",
        "source_type": "rss", "tier": "C", "base_confidence": 0.72, "language": "en",
        "feed_url": "https://www.ethiopia-insight.com/feed/",
        "topics": ["conflict", "coup", "protest"],
        "geo_focus": ["ET", "AF"],
    },
    {
        "display_name": "The Moscow Times",
        "source_type": "rss", "tier": "C", "base_confidence": 0.75, "language": "en",
        "feed_url": "https://www.themoscowtimes.com/rss/news",
        "topics": ["conflict", "sanctions", "protest", "diplomacy"],
        "geo_focus": ["RU", "UA", "EU"],
    },
    {
        "display_name": "Meduza (Russia EN)",
        "source_type": "rss", "tier": "C", "base_confidence": 0.76, "language": "en",
        "feed_url": "https://meduza.io/en/rss/all",
        "topics": ["conflict", "protest", "sanctions", "coup"],
        "geo_focus": ["RU", "UA", "BY", "EU"],
    },
    {
        "display_name": "Caucasus Watch",
        "source_type": "rss", "tier": "C", "base_confidence": 0.72, "language": "en",
        "feed_url": "https://caucasuswatch.de/feed/",
        "topics": ["conflict", "diplomacy", "coup"],
        "geo_focus": ["GE", "AM", "AZ", "TR", "RU"],
    },
    {
        "display_name": "The Irrawaddy (Myanmar)",
        "source_type": "rss", "tier": "C", "base_confidence": 0.78, "language": "en",
        "feed_url": "https://www.irrawaddy.com/feed",
        "topics": ["conflict", "coup", "protest"],
        "geo_focus": ["MM", "AS"],
    },
    {
        "display_name": "Agencia EFE (English)",
        "source_type": "rss", "tier": "C", "base_confidence": 0.75, "language": "en",
        "feed_url": "https://www.efe.com/efe/english/world/rss",
        "topics": ["conflict", "diplomacy", "coup", "protest"],
        "geo_focus": ["global", "LA", "EU", "ME"],
    },
]

_INSERT_SQL = sa.text("""
    INSERT INTO source_channels
      (display_name, source_type, tier, base_confidence, language,
       feed_url, topics, geo_focus, is_active)
    SELECT
      :display_name, :source_type, :tier, :base_confidence, :language,
      :feed_url, :topics, :geo_focus, true
    WHERE NOT EXISTS (
      SELECT 1 FROM source_channels WHERE feed_url = :feed_url
    )
""").bindparams(
    sa.bindparam("topics", type_=sa.ARRAY(sa.Text())),
    sa.bindparam("geo_focus", type_=sa.ARRAY(sa.Text())),
)


def upgrade() -> None:
    conn = op.get_bind()
    for ch in MORE_RSS_CHANNELS:
        conn.execute(_INSERT_SQL, {
            "display_name": ch["display_name"],
            "source_type": ch["source_type"],
            "tier": ch["tier"],
            "base_confidence": ch["base_confidence"],
            "language": ch["language"],
            "feed_url": ch["feed_url"],
            "topics": ch["topics"],
            "geo_focus": ch["geo_focus"],
        })


def downgrade() -> None:
    feeds = [ch["feed_url"] for ch in MORE_RSS_CHANNELS]
    conn = op.get_bind()
    for feed_url in feeds:
        conn.execute(
            sa.text("DELETE FROM source_channels WHERE feed_url = :feed_url"),
            {"feed_url": feed_url},
        )
