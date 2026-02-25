"""
수집기(TelegramCollector, RSSCollector) 단위/통합 테스트.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent
from worker.collector.telegram_collector import TelegramCollector
from worker.collector.rss_collector import RSSCollector, _compute_guid, _extract_text


def _make_telethon_message(
    msg_id=1001,
    text="BREAKING: Multiple explosions reported in Kyiv. Air defense systems activated.",
    channel_id=1234567890,
    views=15000,
    forwards=500,
    replies_count=100,
    has_media=False,
    date=None,
):
    """Telethon Message mock 생성 헬퍼."""
    from telethon.tl.types import Message as TelethonMessage

    msg = MagicMock(spec=TelethonMessage)
    msg.id = msg_id
    msg.text = text
    msg.message = text
    msg.date = date or datetime(2024, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    msg.views = views
    msg.forwards = forwards
    msg.media = MagicMock() if has_media else None

    replies_mock = MagicMock()
    replies_mock.replies = replies_count
    msg.replies = replies_mock

    peer_id_mock = MagicMock()
    peer_id_mock.channel_id = channel_id
    # chat_id 속성이 없도록 설정
    if hasattr(peer_id_mock, "chat_id"):
        del peer_id_mock.chat_id
    msg.peer_id = peer_id_mock

    return msg


# ─── TelegramCollector 단위 테스트 ──────────────────────────────────────────

class TestTelegramCollectorParsing:
    """_parse_message() 테스트 (DB 불필요)."""

    def setup_method(self):
        self.collector = TelegramCollector()
        self.channel = MagicMock(spec=SourceChannel)
        self.channel.id = 1
        self.channel.channel_id = -1001234567890
        self.channel.tier = "B"

    def test_parse_normal_message(self):
        """정상 텍스트 메시지 파싱."""
        msg = _make_telethon_message()
        result = self.collector._parse_message(msg, self.channel)
        assert result is not None
        assert result["source_type"] == "telegram"
        assert "explosions" in result["raw_text"].lower()
        assert result["source_channel_id"] == 1
        assert result["raw_metadata"]["views"] == 15000
        assert result["raw_metadata"]["forwards"] == 500

    def test_parse_media_only_message(self):
        """미디어만 있고 텍스트 없는 메시지 → None 반환."""
        msg = _make_telethon_message(msg_id=1002, text="", has_media=True)
        result = self.collector._parse_message(msg, self.channel)
        assert result is None

    def test_parse_empty_text_message(self):
        """텍스트가 10자 미만인 메시지 → None 반환."""
        msg = _make_telethon_message(msg_id=1003, text="OK")
        result = self.collector._parse_message(msg, self.channel)
        assert result is None

    def test_parse_has_media_flag(self):
        """미디어가 있는 메시지 → has_media=True."""
        msg = _make_telethon_message(
            msg_id=1004,
            text="Drone footage shows damage to Kyiv bridge infrastructure. Multiple impacts visible.",
            has_media=True,
        )
        result = self.collector._parse_message(msg, self.channel)
        assert result is not None
        assert "Kyiv" in result["raw_text"]
        assert result["raw_metadata"]["has_media"] is True

    def test_external_id_format(self):
        """external_id = -100{channel_id}_{message_id} 형식 확인."""
        msg = _make_telethon_message()
        result = self.collector._parse_message(msg, self.channel)
        assert result is not None
        assert result["external_id"] == "-1001234567890_1001"

    def test_parse_replies_count(self):
        """replies 수가 메타데이터에 포함되는지 확인."""
        msg = _make_telethon_message(replies_count=42)
        result = self.collector._parse_message(msg, self.channel)
        assert result is not None
        assert result["raw_metadata"]["replies"] == 42

    def test_parse_no_replies(self):
        """replies가 None일 때 0으로 처리."""
        msg = _make_telethon_message()
        msg.replies = None
        result = self.collector._parse_message(msg, self.channel)
        assert result is not None
        assert result["raw_metadata"]["replies"] == 0


class TestTelegramCollectorIntegration:
    """collect_channel() DB 연동 통합 테스트."""

    @pytest.mark.asyncio
    async def test_collect_and_save(self, db, sample_source_channel_data, redis_mock):
        """정상 메시지 수집 → raw_events 저장 확인."""
        from sqlalchemy import select

        channel = SourceChannel(**sample_source_channel_data)
        channel.channel_id = -1001234567890
        channel.username = "TestOSINT"
        db.add(channel)
        await db.flush()

        msg = _make_telethon_message()

        mock_client = AsyncMock()
        mock_client.get_messages = AsyncMock(return_value=[msg])

        collector = TelegramCollector()
        result = await collector.collect_channel(channel, db, mock_client, redis_mock)

        assert result.collected == 1
        assert result.skipped == 0

        events = await db.execute(
            select(RawEvent).where(RawEvent.source_type == "telegram")
        )
        raw_events = events.scalars().all()
        assert len(raw_events) == 1
        assert "explosions" in raw_events[0].raw_text.lower()

    @pytest.mark.asyncio
    async def test_duplicate_message_skipped(self, db, sample_source_channel_data, redis_mock):
        """같은 메시지 두 번 수집 시 두 번째는 건너뜀."""
        channel = SourceChannel(**sample_source_channel_data)
        channel.channel_id = -1001234567890
        channel.username = "TestOSINT"
        db.add(channel)
        await db.flush()

        msg = _make_telethon_message()

        mock_client = AsyncMock()
        mock_client.get_messages = AsyncMock(return_value=[msg])

        collector = TelegramCollector()

        result1 = await collector.collect_channel(channel, db, mock_client, redis_mock)
        assert result1.collected == 1

        result2 = await collector.collect_channel(channel, db, mock_client, redis_mock)
        assert result2.collected == 0
        assert result2.skipped == 1

    @pytest.mark.asyncio
    async def test_no_username_returns_error(self, db, sample_source_channel_data, redis_mock):
        """username 없는 채널 → 에러 반환."""
        channel = SourceChannel(**sample_source_channel_data)
        channel.channel_id = -1001234567890
        channel.username = None
        db.add(channel)
        await db.flush()

        mock_client = AsyncMock()
        collector = TelegramCollector()
        result = await collector.collect_channel(channel, db, mock_client, redis_mock)

        assert result.collected == 0
        assert len(result.errors) > 0
        assert "username" in result.errors[0]


# ─── RSSCollector 단위 테스트 ────────────────────────────────────────────────

class TestRSSHelpers:
    """RSS 헬퍼 함수 단위 테스트."""

    def test_compute_guid_with_id(self, sample_rss_entry):
        """entry.id가 있으면 그것을 guid로 사용."""
        guid = _compute_guid(sample_rss_entry)
        assert guid == sample_rss_entry["id"]

    def test_compute_guid_without_id(self):
        """entry.id 없으면 link + published MD5 해시."""
        entry = {
            "link": "https://example.com/article",
            "title": "Test Article",
            "published": "2026-02-22",
        }
        guid = _compute_guid(entry)
        assert len(guid) == 32  # MD5 hex digest

    def test_compute_guid_fallback(self):
        """link도 없을 때 title + published MD5."""
        entry = {"title": "Emergency Article", "published": "2026-02-22"}
        guid = _compute_guid(entry)
        assert len(guid) == 32

    def test_extract_text_from_summary(self, sample_rss_entry):
        """summary에서 텍스트 추출."""
        text = _extract_text(sample_rss_entry)
        assert "missile" in text.lower() or "ukraine" in text.lower()

    def test_extract_text_strips_html(self):
        """HTML 태그 제거 확인."""
        entry = {"summary": "<p>Test <b>article</b> content here.</p>"}
        text = _extract_text(entry)
        assert "<" not in text
        assert "Test article content here." == text.strip()

    def test_extract_text_fallback_to_title(self):
        """summary/content 없으면 title 사용."""
        entry = {"title": "Emergency situation reported"}
        text = _extract_text(entry)
        assert text == "Emergency situation reported"


class TestRSSCollectorIntegration:
    """collect_feed() DB 연동 통합 테스트."""

    @pytest.mark.asyncio
    async def test_collect_real_rss_mock(self, db):
        """feedparser Mock으로 RSS 수집 테스트."""
        from unittest.mock import patch
        from sqlalchemy import select

        channel = SourceChannel(
            display_name="Reuters World",
            tier="A",
            base_confidence=0.85,
            language="en",
            topics=["conflict"],
            geo_focus=[],
            source_type="rss",
            feed_url="https://feeds.reuters.com/reuters/worldNews",
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [
            {
                "id": "https://reuters.com/test-001",
                "title": "Ukraine missile strikes reported",
                "summary": "Multiple missile strikes targeting Ukrainian infrastructure confirmed by officials.",
                "link": "https://reuters.com/test-001",
                "published": "Tue, 22 Feb 2026 10:00:00 GMT",
                "published_parsed": (2026, 2, 22, 10, 0, 0, 1, 53, 0),
            }
        ]

        with patch("worker.collector.rss_collector.feedparser.parse", return_value=mock_parsed):
            collector = RSSCollector()
            result = await collector.collect_feed(channel, db)

        assert result.collected == 1
        assert result.skipped == 0
        assert len(result.errors) == 0

        # DB 확인
        events = await db.execute(
            select(RawEvent).where(RawEvent.source_type == "rss")
        )
        raw_events = events.scalars().all()
        assert len(raw_events) == 1
        assert "missile" in raw_events[0].raw_text.lower()

    @pytest.mark.asyncio
    async def test_duplicate_guid_skipped(self, db):
        """같은 GUID의 RSS 항목 두 번 수집 시 건너뜀."""
        from unittest.mock import patch

        channel = SourceChannel(
            display_name="BBC World",
            tier="A",
            base_confidence=0.85,
            language="en",
            topics=["conflict"],
            geo_focus=[],
            source_type="rss",
            feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        mock_entry = {
            "id": "bbc-unique-001",
            "summary": "Breaking news from BBC about international situation.",
            "link": "https://bbc.co.uk/001",
            "published_parsed": (2026, 2, 22, 10, 0, 0, 1, 53, 0),
        }
        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [mock_entry]

        with patch("worker.collector.rss_collector.feedparser.parse", return_value=mock_parsed):
            collector = RSSCollector()
            result1 = await collector.collect_feed(channel, db)
            assert result1.collected == 1

            result2 = await collector.collect_feed(channel, db)
            assert result2.collected == 0
            assert result2.skipped == 1

    @pytest.mark.asyncio
    async def test_no_feed_url_returns_error(self, db):
        """feed_url 없는 채널 → 에러 반환."""
        channel = SourceChannel(
            display_name="No URL Channel",
            tier="B",
            base_confidence=0.70,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="rss",
            feed_url=None,
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        collector = RSSCollector()
        result = await collector.collect_feed(channel, db)
        assert result.collected == 0
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_short_content_skipped(self, db):
        """10자 미만 본문 → 건너뜀."""
        from unittest.mock import patch

        channel = SourceChannel(
            display_name="Short Content Test",
            tier="C",
            base_confidence=0.55,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="rss",
            feed_url="https://example.com/rss",
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [
            {"id": "short-001", "summary": "OK", "title": "OK"}  # 너무 짧음
        ]

        with patch("worker.collector.rss_collector.feedparser.parse", return_value=mock_parsed):
            collector = RSSCollector()
            result = await collector.collect_feed(channel, db)
        assert result.skipped == 1
        assert result.collected == 0
