"""
source_channels 초기 씨드 데이터.
테스트 및 개발용 OSINT 채널 5개 + RSS 2개.
실제 운영 시 신뢰도 검증 후 추가할 것.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.source_channel import SourceChannel
from sqlalchemy import select

# 씨드 데이터: Telegram OSINT 채널 예시 (실제 channel_id는 직접 확인 필요)
TELEGRAM_CHANNELS = [
    {
        "channel_id": None,           # 실제 채널 ID로 교체 필요
        "username": "IntelSlava",     # @IntelSlava (우크라이나/러시아 OSINT)
        "display_name": "Intel Slava Z",
        "tier": "C",
        "base_confidence": 0.55,
        "language": "ru",
        "topics": ["conflict", "military"],
        "geo_focus": ["UA", "RU"],
        "source_type": "telegram",
        "is_active": False,           # 실제 Bot API 연동 전까지 비활성
    },
    {
        "channel_id": None,
        "username": "OSINTdefender",  # @OSINTdefender
        "display_name": "OSINT Defender",
        "tier": "B",
        "base_confidence": 0.70,
        "language": "en",
        "topics": ["conflict", "cyber", "terror"],
        "geo_focus": [],
        "source_type": "telegram",
        "is_active": False,
    },
    {
        "channel_id": None,
        "username": "GeoConfirmed",   # @GeoConfirmed
        "display_name": "GeoConfirmed",
        "tier": "B",
        "base_confidence": 0.72,
        "language": "en",
        "topics": ["conflict", "military"],
        "geo_focus": [],
        "source_type": "telegram",
        "is_active": False,
    },
    {
        "channel_id": None,
        "username": "warmonitor1",    # @warmonitor1
        "display_name": "War Monitor",
        "tier": "C",
        "base_confidence": 0.58,
        "language": "en",
        "topics": ["conflict", "military"],
        "geo_focus": [],
        "source_type": "telegram",
        "is_active": False,
    },
    {
        "channel_id": None,
        "username": "hacktivist1",    # 사이버 OSINT 예시
        "display_name": "Cyber Monitor",
        "tier": "C",
        "base_confidence": 0.55,
        "language": "en",
        "topics": ["cyber"],
        "geo_focus": [],
        "source_type": "telegram",
        "is_active": False,
    },
]

# RSS 소스 (공식/주요언론 - Tier A/B)
RSS_SOURCES = [
    {
        "channel_id": None,
        "username": None,
        "display_name": "Reuters - World News",
        "tier": "A",
        "base_confidence": 0.85,
        "language": "en",
        "topics": ["conflict", "sanctions", "diplomacy", "protest"],
        "geo_focus": [],
        "source_type": "rss",
        "feed_url": "https://feeds.reuters.com/reuters/worldNews",
        "is_active": True,
    },
    {
        "channel_id": None,
        "username": None,
        "display_name": "BBC News - World",
        "tier": "A",
        "base_confidence": 0.85,
        "language": "en",
        "topics": ["conflict", "terror", "coup", "sanctions", "protest"],
        "geo_focus": [],
        "source_type": "rss",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "is_active": True,
    },
]


async def seed():
    print("source_channels 씨드 시작...")
    async with AsyncSessionLocal() as db:
        seeded = 0
        for data in TELEGRAM_CHANNELS + RSS_SOURCES:
            # 이미 존재하는지 확인 (display_name 기준)
            existing = await db.execute(
                select(SourceChannel).where(
                    SourceChannel.display_name == data["display_name"]
                )
            )
            if existing.scalar_one_or_none():
                print(f"  이미 존재: {data['display_name']}")
                continue

            channel = SourceChannel(**data)
            db.add(channel)
            seeded += 1
            print(f"  추가됨 [{data['tier']}]: {data['display_name']}")

        await db.commit()
        print(f"\n씨드 완료: {seeded}개 추가됨")


if __name__ == "__main__":
    asyncio.run(seed())
