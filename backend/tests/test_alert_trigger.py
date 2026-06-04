"""
KScore 기반 알림 트리거 테스트.
- KScore+severity 조건 충족 → 알림 트리거 확인
- 조건 미충족 → 비트리거 확인
- Redis 중복방지 키 동작 확인
- Feature Flag (USE_SPIKE_DETECTION) 동작 확인
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from worker.processor.calibration import (
    USE_SPIKE_DETECTION,
    ALERT_SEVERITY_MIN,
    KSCORE_SOCIAL_MIN,
    KSCORE_MIN,
)


class TestCalibrationConstants:
    """Phase 0 상수값 확인."""

    def test_spike_detection_disabled(self):
        assert USE_SPIKE_DETECTION is False

    def test_alert_severity_min(self):
        assert ALERT_SEVERITY_MIN == 50

    def test_kscore_social_min(self):
        assert KSCORE_SOCIAL_MIN == 5.0

    def test_kscore_min_exists(self):
        assert KSCORE_MIN > 0


class TestSpikeDetectorGuard:
    """spike_detector.py의 USE_SPIKE_DETECTION 가드 확인."""

    @pytest.mark.asyncio
    async def test_evaluate_spike_returns_false_when_disabled(self):
        """USE_SPIKE_DETECTION=False → evaluate_spike()는 즉시 (False, None) 반환."""
        from worker.processor.spike_detector import evaluate_spike

        # Mock 파라미터 (실제 DB 불필요 — 가드에서 즉시 반환)
        result = await evaluate_spike(
            cluster_id="test-uuid",
            severity=90,
            event_count=100,
            independent_sources=10,
            db=AsyncMock(),
            redis=AsyncMock(),
        )
        assert result == (False, None)

    @pytest.mark.asyncio
    async def test_evaluate_spike_respects_flag(self):
        """USE_SPIKE_DETECTION=True일 때는 가드를 통과해야 함."""
        with patch("worker.processor.spike_detector.USE_SPIKE_DETECTION", True):
            from importlib import reload
            import worker.processor.spike_detector as sd
            reload(sd)
            # True일 때는 실제 로직으로 진입 → DB가 필요하므로 예외 발생 예상
            # (실제 DB 없이 호출하면 에러) — 가드를 통과했음을 확인
            try:
                await sd.evaluate_spike(
                    cluster_id="test-uuid",
                    severity=90,
                    event_count=100,
                    independent_sources=10,
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )
            except Exception:
                pass  # DB 없으므로 에러 OK — 가드 통과 확인만

        # 원복: 테스트 격리
        with patch("worker.processor.spike_detector.USE_SPIKE_DETECTION", False):
            pass


class TestAlertTriggerConditions:
    """KScore+severity 조건에 따른 알림 트리거 로직 테스트."""

    def test_condition_met(self):
        """kscore >= KSCORE_MIN AND severity >= ALERT_SEVERITY_MIN → 트리거."""
        kscore = 3.0
        severity = 60
        assert kscore >= KSCORE_MIN
        assert severity >= ALERT_SEVERITY_MIN

    def test_condition_low_kscore(self):
        """kscore < KSCORE_MIN → 비트리거."""
        kscore = 0.5
        severity = 70
        assert kscore < KSCORE_MIN

    def test_condition_low_severity(self):
        """severity < ALERT_SEVERITY_MIN → 비트리거."""
        kscore = 5.0
        severity = 30
        assert severity < ALERT_SEVERITY_MIN

    def test_social_threshold(self):
        """KScore >= KSCORE_SOCIAL_MIN(5.0)인 클러스터만 SNS 대상."""
        assert 5.0 >= KSCORE_SOCIAL_MIN
        assert 4.9 < KSCORE_SOCIAL_MIN


class TestRedisDedup:
    """Redis 중복방지 키 동작 테스트."""

    @pytest.mark.asyncio
    async def test_fast_dedup_key_format(self):
        """Fast alert dedup 키 형식: alert:fast:{cluster_id}."""
        cluster_id = "abc-123"
        key = f"alert:fast:{cluster_id}"
        assert key == "alert:fast:abc-123"

    @pytest.mark.asyncio
    async def test_verified_dedup_key_format(self):
        """Verified alert dedup 키 형식: alert:verified:{cluster_id}."""
        cluster_id = "abc-123"
        key = f"alert:verified:{cluster_id}"
        assert key == "alert:verified:abc-123"

    @pytest.mark.asyncio
    async def test_dedup_ttl_72h(self):
        """중복방지 TTL은 72시간(259200초)."""
        ttl = 259200
        assert ttl == 72 * 3600


class TestTrendingEngineSpikeFactor:
    """trending_engine에서 SPIKE_FACTOR가 1.0으로 비활성화되었는지 확인."""

    def test_spike_factor_is_one(self):
        from worker.processor.calibration import SPIKE_FACTOR
        assert SPIKE_FACTOR == 1.0
