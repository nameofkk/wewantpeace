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


# ── tension_level 분류 ────────────────────────────────────────────────────────

class TestTensionLevel:
    def test_stable(self):
        assert _tension_level(0) == 0
        assert _tension_level(24) == 0

    def test_caution(self):
        assert _tension_level(25) == 1
        assert _tension_level(49) == 1

    def test_alert(self):
        assert _tension_level(50) == 2
        assert _tension_level(74) == 2

    def test_crisis(self):
        assert _tension_level(75) == 3
        assert _tension_level(100) == 3


# ── event_score ───────────────────────────────────────────────────────────────

from types import SimpleNamespace

def _make_cluster(severity: int = 55, confidence: float = 0.70):
    return SimpleNamespace(severity=severity, confidence=confidence)


class TestEventScore:
    def test_empty_clusters(self):
        assert _calc_event_score([]) == 0.0

    def test_single_cluster(self):
        score = _calc_event_score([_make_cluster(100, 1.0)])
        assert score == pytest.approx(100.0)

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
    def test_zero_prev_with_current(self):
        """이전 0에서 현재 10 → 최대 1.0."""
        score = _calc_accel_score(10, 0)
        assert score == pytest.approx(1.0)

    def test_no_change(self):
        """변화 없으면 0."""
        score = _calc_accel_score(5, 5)
        assert score == pytest.approx(0.0)

    def test_decrease(self):
        """감소하면 0 (음수 없음)."""
        score = _calc_accel_score(2, 10)
        assert score == 0.0

    def test_capped_at_1(self):
        """최대 1.0."""
        score = _calc_accel_score(1000, 1)
        assert score == pytest.approx(1.0)

    def test_moderate_increase(self):
        """50% 증가."""
        score = _calc_accel_score(15, 10)
        # (15-10)/(10+1) ≈ 0.45
        assert score == pytest.approx(0.45, abs=0.01)


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
        assert score == pytest.approx(0.80)

    def test_multiple_neighbors_max(self):
        neighbor_clusters = {
            "RU": [_make_cluster(severity=60)],
            "BY": [_make_cluster(severity=90)],
        }
        score = _calc_spillover("UA", neighbor_clusters)
        assert score == pytest.approx(0.90)

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
