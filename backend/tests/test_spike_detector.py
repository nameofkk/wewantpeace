"""
SpikeDetector 단위 테스트.
"""
import pytest
from worker.processor.spike_detector import (
    evaluate_spike,
    increment_event_counters,
    is_in_cooldown,
    set_cooldown,
    update_baseline,
    get_baseline,
    C1_THRESHOLD,
    C10_THRESHOLD,
    RATIO_THRESHOLD,
    SEVERITY_MIN,
)


CLUSTER_ID = "test-cluster-001"
CLUSTER_KEY = "u8c3m:conflict"


# ── 카운터 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_counter_increments(redis_mock):
    c1, c10 = await increment_event_counters(CLUSTER_ID, redis_mock)
    assert c1 == 1
    assert c10 == 1


@pytest.mark.asyncio
async def test_counter_accumulates(redis_mock):
    for _ in range(5):
        await increment_event_counters(CLUSTER_ID, redis_mock)
    c1, c10 = await increment_event_counters(CLUSTER_ID, redis_mock)
    assert c1 == 6
    assert c10 == 6


# ── EWMA 기준선 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_baseline_starts_at_zero(redis_mock):
    b = await get_baseline("new_key", redis_mock)
    assert b == 0.0


@pytest.mark.asyncio
async def test_baseline_updates(redis_mock):
    b = await update_baseline(CLUSTER_KEY, 10, redis_mock)
    # alpha=0.3: 0.3*10 + 0.7*0 = 3.0
    assert b == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_baseline_ewma_converges(redis_mock):
    """반복 업데이트 시 c10 값으로 수렴."""
    for _ in range(50):
        await update_baseline(CLUSTER_KEY, 8, redis_mock)
    b = await get_baseline(CLUSTER_KEY, redis_mock)
    assert b == pytest.approx(8.0, abs=0.5)


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


# ── 스파이크 감지: 트리거 ON ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spike_triggers_on_c1_threshold(redis_mock):
    """c1 >= 4 이면 (ratio 조건도 기준선 0이면 높음) 스파이크."""
    cid = "spike-c1-test"
    ckey = "abc12:conflict"
    # c1을 4 이상으로 만들기 위해 3번 미리 증가
    for _ in range(3):
        await increment_event_counters(cid, redis_mock)
    # 4번째 호출 (evaluate_spike 내부에서 1회 더 증가)
    result = await evaluate_spike(cid, ckey, severity=55, redis=redis_mock)
    assert result is True


@pytest.mark.asyncio
async def test_spike_triggers_on_c10_threshold(redis_mock):
    """c10 >= 12 면 스파이크."""
    cid = "spike-c10-test"
    ckey = "def34:conflict"
    # 11번 미리 증가
    for _ in range(11):
        await increment_event_counters(cid, redis_mock)
    result = await evaluate_spike(cid, ckey, severity=55, redis=redis_mock)
    assert result is True


# ── 스파이크 감지: 트리거 OFF ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spike_not_triggered_low_severity(redis_mock):
    """severity < 35 면 스파이크 안됨."""
    cid = "no-spike-sev"
    ckey = "ghi56:diplomacy"
    for _ in range(20):
        await increment_event_counters(cid, redis_mock)
    result = await evaluate_spike(cid, ckey, severity=20, redis=redis_mock)
    assert result is False


@pytest.mark.asyncio
async def test_spike_not_triggered_low_count(redis_mock):
    """c1 < 4 AND c10 < 12 면 스파이크 안됨."""
    cid = "no-spike-count"
    ckey = "jkl78:protest"
    # 카운터 없는 상태 → evaluate_spike 1회만 호출 → c1=1, c10=1
    result = await evaluate_spike(cid, ckey, severity=60, redis=redis_mock)
    assert result is False


@pytest.mark.asyncio
async def test_spike_cooldown_prevents_retrigger(redis_mock):
    """쿨다운 중이면 스파이크 트리거 안됨."""
    cid = "cooldown-test"
    ckey = "mno90:conflict"
    # 먼저 쿨다운 설정
    await set_cooldown(cid, redis_mock)
    # 카운터 많아도
    for _ in range(20):
        await increment_event_counters(cid, redis_mock)
    result = await evaluate_spike(cid, ckey, severity=80, redis=redis_mock)
    assert result is False


@pytest.mark.asyncio
async def test_spike_ratio_prevents_trigger(redis_mock):
    """ratio < 4.0 이면 스파이크 안됨 (높은 기준선)."""
    cid = "ratio-test"
    ckey = "pqr12:conflict"
    # 기준선을 높게 설정 (c10=100으로 EWMA)
    for _ in range(100):
        await update_baseline(ckey, 100, redis_mock)
    # c10을 11로 (threshold는 12 미만)
    for _ in range(10):
        await increment_event_counters(cid, redis_mock)
    result = await evaluate_spike(cid, ckey, severity=70, redis=redis_mock)
    assert result is False
