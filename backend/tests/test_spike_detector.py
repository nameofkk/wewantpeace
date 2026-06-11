"""
SpikeDetector v2 단위 테스트 — 누적 기반 스파이크 감지.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from worker.processor.spike_detector import (
    evaluate_spike,
    is_in_cooldown,
    set_cooldown,
    EVENT_COUNT_MIN,
    SEVERITY_MIN,
    SOURCES_MIN,
    MAX_AGE_HOURS,
    COOLDOWN_SECONDS,
    COOLDOWN_SECONDS_CRITICAL,
)


CLUSTER_ID = "test-cluster-001"


# ── 쿨다운 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cooldown_initially_false(redis_mock):
    result = await is_in_cooldown("no-cluster", redis_mock)
    assert result is False


@pytest.mark.asyncio
async def test_cooldown_set_and_detected(redis_mock):
    await set_cooldown(CLUSTER_ID, redis_mock)
    result = await is_in_cooldown(CLUSTER_ID, redis_mock)
    assert result is True


@pytest.mark.asyncio
async def test_cooldown_severity_critical_uses_shorter_ttl(redis_mock):
    """severity >= 90 → 3시간 쿨다운."""
    await set_cooldown(CLUSTER_ID, redis_mock, severity=95)
    ttl = await redis_mock.ttl(f"spike:cooldown:{CLUSTER_ID}")
    assert ttl <= COOLDOWN_SECONDS_CRITICAL
    assert ttl > 0


@pytest.mark.asyncio
async def test_cooldown_normal_uses_longer_ttl(redis_mock):
    """severity < 90 → 6시간 쿨다운."""
    await set_cooldown(CLUSTER_ID, redis_mock, severity=50)
    ttl = await redis_mock.ttl(f"spike:cooldown:{CLUSTER_ID}")
    assert ttl <= COOLDOWN_SECONDS
    assert ttl > COOLDOWN_SECONDS_CRITICAL


# ── 스파이크 감지: 트리거 ON ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("worker.processor.calibration.USE_SPIKE_DETECTION", True)  # v7에서 기본 비활성 — 트리거 로직 자체를 검증하려 플래그 ON 패치
@patch("worker.processor.spike_detector._save_spike_event", new_callable=AsyncMock, return_value="spike-id-001")
async def test_spike_triggers_when_all_conditions_met(mock_save, redis_mock):
    """event_count >= 8, severity >= 40, sources >= 3, age <= 48h → 스파이크."""
    result = await evaluate_spike(
        cluster_id=CLUSTER_ID,
        severity=60,
        event_count=10,
        independent_sources=4,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=2),
        kscore=5.5,
        redis=redis_mock,
    )
    is_spike, spike_id = result
    assert is_spike is True
    assert spike_id == "spike-id-001"
    mock_save.assert_called_once()


@pytest.mark.asyncio
@patch("worker.processor.calibration.USE_SPIKE_DETECTION", True)  # v7 비활성 — 트리거 로직 검증용 ON
@patch("worker.processor.spike_detector._save_spike_event", new_callable=AsyncMock, return_value="spike-id-002")
async def test_spike_triggers_at_exact_thresholds(mock_save, redis_mock):
    """정확한 임계치에서도 트리거."""
    result = await evaluate_spike(
        cluster_id="exact-threshold",
        severity=SEVERITY_MIN,
        event_count=EVENT_COUNT_MIN,
        independent_sources=SOURCES_MIN,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is True


# ── 스파이크 감지: 트리거 OFF ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spike_not_triggered_low_severity(redis_mock):
    """severity < 40 → 스파이크 안됨."""
    result = await evaluate_spike(
        cluster_id="no-spike-sev",
        severity=SEVERITY_MIN - 1,
        event_count=20,
        independent_sources=5,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


@pytest.mark.asyncio
async def test_spike_not_triggered_low_event_count(redis_mock):
    """event_count < 8 → 스파이크 안됨."""
    result = await evaluate_spike(
        cluster_id="no-spike-count",
        severity=60,
        event_count=EVENT_COUNT_MIN - 1,
        independent_sources=5,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


@pytest.mark.asyncio
async def test_spike_not_triggered_low_sources(redis_mock):
    """independent_sources < 3 → 스파이크 안됨."""
    result = await evaluate_spike(
        cluster_id="no-spike-sources",
        severity=60,
        event_count=20,
        independent_sources=SOURCES_MIN - 1,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


@pytest.mark.asyncio
async def test_spike_not_triggered_old_cluster(redis_mock):
    """cluster age > 48h → 스파이크 안됨."""
    result = await evaluate_spike(
        cluster_id="no-spike-old",
        severity=80,
        event_count=30,
        independent_sources=10,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS + 1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


@pytest.mark.asyncio
async def test_spike_not_triggered_no_first_event(redis_mock):
    """first_event_at=None → age=0 → 조건 충족 시 트리거 가능 (age_hours=0 <= 48)."""
    # first_event_at=None이면 age_hours=0이므로 age 조건은 통과
    # 하지만 낮은 severity로 막음
    result = await evaluate_spike(
        cluster_id="no-first-event",
        severity=10,
        event_count=20,
        independent_sources=5,
        first_event_at=None,
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


@pytest.mark.asyncio
async def test_spike_cooldown_prevents_retrigger(redis_mock):
    """쿨다운 중이면 스파이크 트리거 안됨."""
    cid = "cooldown-test"
    await set_cooldown(cid, redis_mock)
    result = await evaluate_spike(
        cluster_id=cid,
        severity=80,
        event_count=30,
        independent_sources=10,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    is_spike, _ = result
    assert is_spike is False


# ── 쿨다운 설정 확인 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("worker.processor.calibration.USE_SPIKE_DETECTION", True)  # v7 비활성 — 트리거 로직 검증용 ON
@patch("worker.processor.spike_detector._save_spike_event", new_callable=AsyncMock, return_value="spike-cd")
async def test_spike_sets_cooldown_after_trigger(mock_save, redis_mock):
    """스파이크 발동 후 쿨다운이 자동 설정됨."""
    cid = "cooldown-auto-set"
    assert await is_in_cooldown(cid, redis_mock) is False

    await evaluate_spike(
        cluster_id=cid,
        severity=60,
        event_count=15,
        independent_sources=5,
        first_event_at=datetime.now(timezone.utc) - timedelta(hours=1),
        redis=redis_mock,
    )
    assert await is_in_cooldown(cid, redis_mock) is True


# ── 상수 값 검증 ─────────────────────────────────────────────────────────────

def test_constants():
    """상수가 기대값과 일치하는지 확인."""
    assert EVENT_COUNT_MIN == 8
    assert SEVERITY_MIN == 40
    assert SOURCES_MIN == 3
    assert MAX_AGE_HOURS == 48
    assert COOLDOWN_SECONDS == 21600       # 6시간
    assert COOLDOWN_SECONDS_CRITICAL == 10800  # 3시간
