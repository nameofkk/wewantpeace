"""
pytest 픽스처 설정.
- 비동기 SQLite(aiosqlite) 인메모리 DB
- fakeredis Redis 목
"""
import asyncio
import os
import sys

# 프로젝트 루트를 PATH에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# 테스트용 환경변수 오버라이드 (import 전에 설정)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "test-api-hash")

import pytest
import pytest_asyncio
import fakeredis.aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import event

from backend.app.core.database import Base
import backend.app.models  # noqa: F401 — 모든 모델을 Base.metadata에 등록


# ─── 비동기 DB 픽스처 ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """세션 스코프 이벤트 루프."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """세션 스코프 SQLite 인메모리 비동기 엔진."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        # SQLite에서 외래키 활성화
        await conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(async_engine) -> AsyncSession:
    """테스트별 DB 세션 (롤백으로 격리)."""
    Session = async_sessionmaker(async_engine, expire_on_commit=False)
    async with Session() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ─── Redis Mock 픽스처 ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def redis_mock():
    """fakeredis 비동기 클라이언트."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


# ─── 공통 팩토리 픽스처 ─────────────────────────────────────────────────────

@pytest.fixture
def sample_source_channel_data():
    """SourceChannel 생성용 샘플 데이터."""
    return {
        "display_name": "Test OSINT Channel",
        "tier": "B",
        "base_confidence": 0.70,
        "language": "en",
        "topics": ["conflict", "cyber"],
        "geo_focus": ["UA"],
        "source_type": "telegram",
        "is_active": True,
    }


@pytest.fixture
def sample_telegram_message():
    """Telethon Message mock 객체."""
    from unittest.mock import MagicMock
    from datetime import datetime, timezone

    msg = MagicMock()
    msg.id = 1001
    msg.text = "BREAKING: Multiple explosions reported in Kyiv. Air defense systems activated. Unconfirmed reports of missile strikes."
    msg.message = msg.text
    msg.date = datetime(2024, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    msg.views = 15000
    msg.forwards = 500
    msg.media = None

    # replies mock
    replies_mock = MagicMock()
    replies_mock.replies = 100
    msg.replies = replies_mock

    # peer_id mock (PeerChannel)
    peer_id_mock = MagicMock()
    peer_id_mock.channel_id = 1234567890
    del peer_id_mock.chat_id  # hasattr(peer_id, 'chat_id') → False
    msg.peer_id = peer_id_mock

    # isinstance(msg, Message) 체크를 위해 __class__ 설정
    msg.__class__ = type("Message", (), {})

    return msg


@pytest.fixture
def sample_rss_entry():
    """feedparser entry 샘플."""
    return {
        "id": "https://reuters.com/article/test-123",
        "title": "Ukraine reports missile attacks on Kyiv infrastructure",
        "summary": "Ukrainian officials confirmed multiple missile strikes targeting energy infrastructure in Kyiv on Tuesday.",
        "link": "https://reuters.com/article/test-123",
        "published": "Tue, 22 Feb 2026 10:00:00 GMT",
        "published_parsed": (2026, 2, 22, 10, 0, 0, 1, 53, 0),
    }
