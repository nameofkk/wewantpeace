"""
DB 스키마 제약조건 및 기본값 테스트.
"""
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent
from backend.app.models.user import User, UserArea, UserPreference


class TestTableCreation:
    """모든 테이블이 정상 생성되었는지 확인."""

    @pytest.mark.asyncio
    async def test_all_tables_exist(self, async_engine):
        """주요 테이블 존재 확인."""
        expected_tables = [
            "source_channels",
            "raw_events",
            "normalized_events",
            "issue_clusters",
            "cluster_events",
            "users",
            "user_areas",
            "user_push_tokens",
            "user_preferences",
        ]
        async with async_engine.connect() as conn:
            # SQLite는 sqlite_master로 확인
            for table_name in expected_tables:
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name=:tbl"),
                    {"tbl": table_name},
                )
                row = result.fetchone()
                assert row is not None, f"테이블 '{table_name}'이 존재하지 않음"


class TestSourceChannelConstraints:
    """source_channels 제약조건 테스트."""

    @pytest.mark.asyncio
    async def test_valid_tier_insert(self, db):
        """유효한 tier(A/B/C/D) INSERT 성공."""
        for tier in ["A", "B", "C", "D"]:
            channel = SourceChannel(
                display_name=f"Test Channel {tier}",
                tier=tier,
                base_confidence=0.70,
                language="en",
                topics=[],
                geo_focus=[],
                source_type="telegram",
                is_active=True,
            )
            db.add(channel)
        await db.flush()  # 오류 없이 통과해야 함

    @pytest.mark.asyncio
    async def test_channel_id_unique_constraint(self, db):
        """동일 channel_id 두 번 INSERT → 오류."""
        ch1 = SourceChannel(
            channel_id=-1001234567890,
            display_name="Channel A",
            tier="B",
            base_confidence=0.70,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="telegram",
            is_active=True,
        )
        ch2 = SourceChannel(
            channel_id=-1001234567890,  # 동일 channel_id
            display_name="Channel B",
            tier="C",
            base_confidence=0.55,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="telegram",
            is_active=True,
        )
        db.add(ch1)
        await db.flush()
        db.add(ch2)
        with pytest.raises(Exception):  # IntegrityError (unique constraint)
            await db.flush()

    @pytest.mark.asyncio
    async def test_default_is_active_true(self, db):
        """is_active 기본값이 True인지 확인."""
        channel = SourceChannel(
            display_name="Default Active Test",
            tier="A",
            base_confidence=0.85,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="rss",
        )
        db.add(channel)
        await db.flush()
        assert channel.is_active is True


class TestRawEventConstraints:
    """raw_events 제약조건 테스트."""

    @pytest.mark.asyncio
    async def test_unique_source_external_id(self, db):
        """(source_type, external_id) unique 제약 테스트."""
        channel = SourceChannel(
            display_name="Unique Test Channel",
            tier="B",
            base_confidence=0.70,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="telegram",
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        event1 = RawEvent(
            source_channel_id=channel.id,
            source_type="telegram",
            external_id="-1000000001_101",
            raw_text="First event - conflict situation developing in the region",
            raw_metadata={},
            processed=False,
        )
        db.add(event1)
        await db.flush()

        event2 = RawEvent(
            source_channel_id=channel.id,
            source_type="telegram",
            external_id="-1000000001_101",  # 동일 external_id
            raw_text="Duplicate event - same external_id",
            raw_metadata={},
            processed=False,
        )
        db.add(event2)
        with pytest.raises(Exception):  # unique constraint 위반
            await db.flush()

    @pytest.mark.asyncio
    async def test_processed_default_false(self, db):
        """processed 기본값이 False인지 확인."""
        channel = SourceChannel(
            display_name="Processed Test",
            tier="A",
            base_confidence=0.85,
            language="en",
            topics=[],
            geo_focus=[],
            source_type="rss",
            is_active=True,
        )
        db.add(channel)
        await db.flush()

        event = RawEvent(
            source_channel_id=channel.id,
            source_type="rss",
            external_id="rss-default-processed-test",
            raw_text="Test event content that is long enough to pass validation",
            raw_metadata={},
        )
        db.add(event)
        await db.flush()
        assert event.processed is False


class TestUserAreaConstraints:
    """user_areas 제약조건 테스트."""

    @pytest.mark.asyncio
    async def test_notify_verified_default_true(self, db):
        """notify_verified 기본값이 True인지 확인."""
        user = User(
            firebase_uid="test-firebase-uid-001",
            email="test@example.com",
            plan="free",
        )
        db.add(user)
        await db.flush()

        area = UserArea(
            user_id=user.id,
            area_type="country",
            country_code="KR",
            label="대한민국",
        )
        db.add(area)
        await db.flush()

        assert area.notify_verified is True
        assert area.notify_fast is False  # Fast는 기본 False

    @pytest.mark.asyncio
    async def test_notify_fast_default_false(self, db):
        """notify_fast 기본값이 False인지 확인."""
        user = User(
            firebase_uid="test-firebase-uid-002",
            plan="free",
        )
        db.add(user)
        await db.flush()

        area = UserArea(
            user_id=user.id,
            area_type="country",
            country_code="US",
            label="미국",
        )
        db.add(area)
        await db.flush()
        assert area.notify_fast is False

    @pytest.mark.asyncio
    async def test_user_preferences_defaults(self, db):
        """user_preferences 기본값 확인."""
        user = User(
            firebase_uid="test-firebase-uid-003",
            plan="free",
        )
        db.add(user)
        await db.flush()

        prefs = UserPreference(
            user_id=user.id,
        )
        db.add(prefs)
        await db.flush()

        assert prefs.language == "ko"
        assert prefs.min_severity == 35
        assert prefs.timezone == "Asia/Seoul"

    @pytest.mark.asyncio
    async def test_user_cascade_delete(self, db):
        """User 삭제 시 UserArea도 cascade 삭제."""
        from sqlalchemy import select

        user = User(
            firebase_uid="test-cascade-delete",
            plan="free",
        )
        db.add(user)
        await db.flush()

        area = UserArea(
            user_id=user.id,
            area_type="country",
            country_code="JP",
            label="일본",
        )
        db.add(area)
        await db.flush()

        area_id = area.id
        await db.delete(user)
        await db.flush()

        result = await db.execute(
            select(UserArea).where(UserArea.id == area_id)
        )
        assert result.scalar_one_or_none() is None
