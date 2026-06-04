"""
Deduplicator 단위 테스트.
"""
import pytest
from datetime import datetime, timezone
from worker.processor.deduplicator import check_duplicate
from backend.app.models.normalized_event import NormalizedEvent


NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


async def _make_ne(db, dedup_key: str, is_duplicate: bool = False) -> NormalizedEvent:
    ne = NormalizedEvent(
        raw_event_id=None,
        title="Test Event",
        body="body",
        topic="conflict",
        entity_anchor="UA",
        lat=50.0,
        lon=30.0,
        geohash5="u8c3m",
        country_code="UA",
        severity=55,
        source_tier="B",
        confidence=0.70,
        dedup_key=dedup_key,
        is_duplicate=is_duplicate,
        event_time=NOW,
    )
    db.add(ne)
    await db.flush()
    return ne


@pytest.mark.asyncio
async def test_no_duplicate_when_empty(db):
    result = await check_duplicate("nonexistent_key", db)
    assert result is False


@pytest.mark.asyncio
async def test_detects_duplicate(db):
    await _make_ne(db, "key_abc", is_duplicate=False)
    result = await check_duplicate("key_abc", db)
    assert result is True


@pytest.mark.asyncio
async def test_skips_already_duplicate_records(db):
    """is_duplicate=True인 레코드는 중복 탐지에서 제외."""
    await _make_ne(db, "key_xyz", is_duplicate=True)
    result = await check_duplicate("key_xyz", db)
    assert result is False


@pytest.mark.asyncio
async def test_different_keys_independent(db):
    await _make_ne(db, "key_aaa")
    result = await check_duplicate("key_bbb", db)
    assert result is False


@pytest.mark.asyncio
async def test_multiple_originals_still_duplicate(db):
    """원본이 여러 개여도 True 반환."""
    await _make_ne(db, "key_multi")
    await _make_ne(db, "key_multi", is_duplicate=True)
    result = await check_duplicate("key_multi", db)
    assert result is True
