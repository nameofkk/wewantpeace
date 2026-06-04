"""
TensionCalculator 단위 테스트.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from worker.processor.tension_calculator import (
    _tension_level,
    _calc_event_score,
    _calc_accel_score,
    _calc_spillover,
    NEIGHBOR_MAP,
)


# ── tension_level 분류 (5단계) ────────────────────────────────────────────────

class TestTensionLevel:
    def test_stable(self):
        # raw_score 기반: 0~19 → 0 (안정)
        assert _tension_level(0, 0) == 0
        assert _tension_level(19, 19) == 0

    def test_caution(self):
        # raw_score 기반: 20~39 → 1 (주의)
        assert _tension_level(20, 20) == 1
        assert _tension_level(39, 39) == 1

    def test_alert(self):
        # raw_score 기반: 40~59 → 2 (경계)
        assert _tension_level(40, 40) == 2
        assert _tension_level(59, 59) == 2

    def test_severe(self):
        # raw_score 기반: 60~79 → 3 (심각)
        assert _tension_level(60, 60) == 3
        assert _tension_level(79, 79) == 3

    def test_extreme(self):
        # raw_score 기반: 80~100 → 4 (극심)
        assert _tension_level(80, 80) == 4
        assert _tension_level(100, 100) == 4

    def test_floor_low_raw_score(self):
        """raw_score < 20이면 퍼센타일이 높아도 레벨 0."""
        assert _tension_level(90, 10) == 0

    def test_floor_medium_raw_score(self):
        """raw_score < 40이면 max_level=1."""
        assert _tension_level(90, 25) == 1


# ── event_score ───────────────────────────────────────────────────────────────

from types import SimpleNamespace

def _make_cluster(severity: int = 55, confidence: float = 0.70, event_count: int = 1):
    return SimpleNamespace(severity=severity, confidence=confidence, event_count=event_count)


class TestEventScore:
    def test_empty_clusters(self):
        assert _calc_event_score([]) == 0.0

    def test_single_cluster(self):
        score = _calc_event_score([_make_cluster(100, 1.0)])
        assert 0 < score <= 100

    def test_low_confidence_reduces_score(self):
        high = _calc_event_score([_make_cluster(80, 1.0)])
        low = _calc_event_score([_make_cluster(80, 0.3)])
        assert high > low

    def test_multiple_clusters_average(self):
        clusters = [_make_cluster(60, 0.80), _make_cluster(40, 0.60)]
        score = _calc_event_score(clusters)
        assert 0 < score <= 100


# ── accel_score ───────────────────────────────────────────────────────────────

class TestAccelScore:
    def test_zero_prev_volume_only(self):
        """이전 0에서 현재 100 events, 10 clusters → 볼륨 위주."""
        score = _calc_accel_score(100, 0, 10)
        assert score == pytest.approx(0.6, abs=0.01)  # 0.6 * volume(1.0) + 0.4 * accel(0)

    def test_no_change(self):
        """클러스터 수 변화 없으면 가속도 0, 볼륨만."""
        score = _calc_accel_score(50, 5, 5)
        # volume = 50/100 = 0.5, accel = 0
        assert score == pytest.approx(0.3, abs=0.01)

    def test_decrease(self):
        """감소하면 가속도 0 (음수 없음)."""
        score = _calc_accel_score(20, 10, 5)
        # volume = 0.2, accel = max(0, (5-10)/10) = 0
        assert score == pytest.approx(0.12, abs=0.01)

    def test_growth_increases_score(self):
        """클러스터 수 증가하면 가속도 보너스."""
        no_growth = _calc_accel_score(50, 5, 5)
        growth = _calc_accel_score(50, 5, 10)
        assert growth > no_growth


# ── spillover ─────────────────────────────────────────────────────────────────

class TestSpillover:
    def test_no_neighbors(self):
        score = _calc_spillover("XX", {})
        assert score == 0.0

    def test_neighbor_with_high_severity(self):
        neighbor_clusters = {
            "RU": [_make_cluster(severity=80)],
        }
        score = _calc_spillover("UA", neighbor_clusters)
        # avg_sev=80, (80/100)*0.7 = 0.56
        assert score == pytest.approx(0.56, abs=0.01)

    def test_multiple_neighbors_avg(self):
        neighbor_clusters = {
            "RU": [_make_cluster(severity=60)],
            "BY": [_make_cluster(severity=90)],
        }
        score = _calc_spillover("UA", neighbor_clusters)
        # avg_sev = (60+90)/2 = 75, (75/100)*0.7 = 0.525
        assert score == pytest.approx(0.525, abs=0.01)

    def test_empty_neighbor_clusters(self):
        score = _calc_spillover("UA", {"RU": [], "BY": []})
        assert score == 0.0


# ── 이웃 관계 ─────────────────────────────────────────────────────────────────

class TestNeighborMap:
    def test_ua_neighbors_include_ru(self):
        assert "RU" in NEIGHBOR_MAP["UA"]

    def test_ps_neighbors_include_il(self):
        assert "IL" in NEIGHBOR_MAP["PS"]

    def test_tw_neighbors_include_cn(self):
        assert "CN" in NEIGHBOR_MAP["TW"]
