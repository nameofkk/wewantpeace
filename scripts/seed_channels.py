"""
source_channels 초기 데이터 시드 스크립트.
RSS 뉴스 소스와 Telegram 봇 채널 등록.
"""
import asyncio
import sys
sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.source_channel import SourceChannel
from sqlalchemy import select


RSS_CHANNELS = [
    # Tier A — 주요 국제 뉴스
    dict(display_name="Reuters World News", tier="A", base_confidence=0.90,
         source_type="rss", language="en",
         feed_url="https://feeds.reuters.com/reuters/worldNews",
         topics=["conflict", "diplomacy", "sanctions"],
         geo_focus=[]),
    dict(display_name="BBC World News", tier="A", base_confidence=0.88,
         source_type="rss", language="en",
         feed_url="http://feeds.bbci.co.uk/news/world/rss.xml",
         topics=["conflict", "terror", "diplomacy"],
         geo_focus=[]),
    dict(display_name="Al Jazeera English", tier="A", base_confidence=0.82,
         source_type="rss", language="en",
         feed_url="https://www.aljazeera.com/xml/rss/all.xml",
         topics=["conflict", "protest", "diplomacy"],
         geo_focus=["ME", "AF"]),
    dict(display_name="AP Top Headlines", tier="A", base_confidence=0.90,
         source_type="rss", language="en",
         feed_url="https://feeds.apnews.com/rss/apf-topnews",
         topics=["conflict", "coup", "terror"],
         geo_focus=[]),

    # Tier B — 전문 안보 / 지역 뉴스
    dict(display_name="Defense News", tier="B", base_confidence=0.75,
         source_type="rss", language="en",
         feed_url="https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
         topics=["conflict", "maritime"],
         geo_focus=[]),
    dict(display_name="The Guardian World", tier="B", base_confidence=0.78,
         source_type="rss", language="en",
         feed_url="https://www.theguardian.com/world/rss",
         topics=["conflict", "protest", "diplomacy"],
         geo_focus=[]),
    dict(display_name="Foreign Policy", tier="B", base_confidence=0.80,
         source_type="rss", language="en",
         feed_url="https://foreignpolicy.com/feed/",
         topics=["diplomacy", "sanctions", "conflict"],
         geo_focus=[]),

    # Tier C — 추가 소스
    dict(display_name="Bellingcat", tier="C", base_confidence=0.70,
         source_type="rss", language="en",
         feed_url="https://www.bellingcat.com/feed/",
         topics=["conflict", "cyber", "terror"],
         geo_focus=[]),
    dict(display_name="Relief Web", tier="C", base_confidence=0.65,
         source_type="rss", language="en",
         feed_url="https://reliefweb.int/headlines/rss.xml",
         topics=["conflict", "protest"],
         geo_focus=[]),
]

TELEGRAM_CHANNELS = [
    # 봇 자신이 멤버인 채널만 getUpdates로 수집 가능
    # channel_id=None → 모든 업데이트 수집 (테스트용)
    dict(display_name="WeWantPeaceBot Direct", tier="C", base_confidence=0.55,
         source_type="telegram", language=None,
         channel_id=None, username="WeWantPeace_bot",
         topics=[], geo_focus=[]),
]


async def seed():
    async with AsyncSessionLocal() as db:
        async with db.begin():
            added = 0
            for ch_data in RSS_CHANNELS + TELEGRAM_CHANNELS:
                # 이미 있으면 스킵 (feed_url 또는 display_name 기준)
                feed_url = ch_data.get("feed_url")
                if feed_url:
                    existing = await db.execute(
                        select(SourceChannel).where(SourceChannel.feed_url == feed_url)
                    )
                else:
                    existing = await db.execute(
                        select(SourceChannel).where(
                            SourceChannel.display_name == ch_data["display_name"]
                        )
                    )
                if existing.scalar_one_or_none():
                    print(f"  SKIP (already exists): {ch_data['display_name']}")
                    continue

                ch = SourceChannel(
                    display_name=ch_data["display_name"],
                    tier=ch_data["tier"],
                    base_confidence=ch_data["base_confidence"],
                    source_type=ch_data["source_type"],
                    language=ch_data.get("language"),
                    feed_url=ch_data.get("feed_url"),
                    channel_id=ch_data.get("channel_id"),
                    username=ch_data.get("username"),
                    topics=ch_data.get("topics", []),
                    geo_focus=ch_data.get("geo_focus", []),
                    is_active=True,
                )
                db.add(ch)
                added += 1
                print(f"  ADD: [{ch_data['tier']}] {ch_data['display_name']}")

            print(f"\n완료: {added}개 채널 추가됨")


if __name__ == "__main__":
    asyncio.run(seed())
