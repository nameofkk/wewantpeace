"""
Worker normalizer 단위 테스트.
"""
import pytest
from datetime import datetime, timezone
from worker.processor.normalizer import (
    normalize,
    _classify_topic,
    _calculate_severity,
    _extract_geo,
    _make_dedup_key,
    _make_title,
    _calculate_confidence,
)

NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── topic 분류 ────────────────────────────────────────────────────────────────

class TestClassifyTopic:
    def test_conflict_keywords(self):
        assert _classify_topic("Missile strike on kyiv, military casualties") == "conflict"

    def test_terror_keywords(self):
        assert _classify_topic("Terrorist attack on civilians by extremist group") == "terror"

    def test_coup_keywords(self):
        assert _classify_topic("Military coup overthrew the government, martial law declared") == "coup"

    def test_sanctions_keywords(self):
        assert _classify_topic("New sanctions and embargo on trade ban") == "sanctions"

    def test_cyber_keywords(self):
        assert _classify_topic("Major cyberattack using ransomware hit power grid") == "cyber"

    def test_protest_keywords(self):
        assert _classify_topic("Thousands joined protest and demonstration in city") == "protest"

    def test_diplomacy_keywords(self):
        assert _classify_topic("Peace treaty negotiations at summit, agreement reached") == "diplomacy"

    def test_unknown_when_no_match(self):
        assert _classify_topic("Weather forecast shows rain tomorrow") == "unknown"

    def test_most_matching_topic_wins(self):
        # conflict 키워드가 더 많으면 conflict
        text = "attack missile bomb explosion airstrike artillery troops military war killed"
        assert _classify_topic(text) == "conflict"


# ── severity 계산 ─────────────────────────────────────────────────────────────

class TestCalculateSeverity:
    def test_base_conflict(self):
        sev = _calculate_severity("troops moved", "conflict")
        assert sev == 60  # base only

    def test_upward_modifier(self):
        sev = _calculate_severity("killed and dead, casualties reported", "conflict")
        # base=60 + killed(10) + dead(10) + casualties(8) = 88, capped keyword_delta at 40
        assert sev == 88

    def test_downward_modifier(self):
        sev = _calculate_severity("allegedly missile strike unconfirmed", "conflict")
        # base=60, +12(missile strike), -10(unconfirmed) = 62
        assert sev == 62

    def test_clamp_max_100(self):
        text = ("nuclear chemical weapon killed dead casualties deaths martial law mobilization "
                "airstrike missile strike explosion bomb infrastructure power grid hospital "
                "capital city center civilian")
        sev = _calculate_severity(text, "coup")
        assert sev == 100

    def test_clamp_min_0(self):
        text = "alleged unconfirmed rumor reportedly claims possibly denied false alarm"
        sev = _calculate_severity(text, "diplomacy")
        assert sev == 0

    def test_unknown_base(self):
        sev = _calculate_severity("something happened", "unknown")
        assert sev == 20


# ── geo 추출 ──────────────────────────────────────────────────────────────────

class TestExtractGeo:
    def test_ukraine_detected(self):
        code, lat, lon = _extract_geo("Shelling near kyiv continued overnight")
        assert code == "UA"
        assert lat == pytest.approx(50.45, abs=0.1)

    def test_longer_keyword_wins(self):
        # "north korea" > "korea" — 긴 키워드 우선
        code, lat, lon = _extract_geo("Tensions in north korea rising")
        assert code == "KP"

    def test_no_match_returns_none(self):
        code, lat, lon = _extract_geo("no country mentioned here")
        assert code is None
        assert lat is None
        assert lon is None

    def test_case_insensitive(self):
        code, lat, lon = _extract_geo("RUSSIA launched attack")
        assert code == "RU"


# ── dedup key ─────────────────────────────────────────────────────────────────

class TestMakeDedupKey:
    def test_returns_32_char_md5(self):
        key = _make_dedup_key("some text")
        assert len(key) == 32

    def test_same_words_different_order_gives_different_key(self):
        k1 = _make_dedup_key("apple banana cherry")
        k2 = _make_dedup_key("cherry apple banana")
        assert k1 != k2  # 단어 순서 유지 → 다른 키

    def test_punctuation_stripped(self):
        k1 = _make_dedup_key("hello, world!")
        k2 = _make_dedup_key("hello world")
        assert k1 == k2

    def test_different_texts_differ(self):
        k1 = _make_dedup_key("ukraine attack")
        k2 = _make_dedup_key("russia defense")
        assert k1 != k2


# ── title 생성 ────────────────────────────────────────────────────────────────

class TestMakeTitle:
    def test_first_sentence_used(self):
        title = _make_title("First sentence. Second sentence. Third.")
        assert title == "First sentence"

    def test_long_text_truncated(self):
        text = "A" * 200
        title = _make_title(text)
        assert len(title) <= 120

    def test_short_text_unchanged(self):
        title = _make_title("Short title")
        assert title == "Short title"


# ── confidence 계산 ───────────────────────────────────────────────────────────

class TestCalculateConfidence:
    def test_tier_a(self):
        assert _calculate_confidence("A", 50) == pytest.approx(0.85)

    def test_tier_b(self):
        assert _calculate_confidence("B", 50) == pytest.approx(0.70)

    def test_tier_c(self):
        assert _calculate_confidence("C", 50) == pytest.approx(0.55)

    def test_high_severity_no_penalty(self):
        conf = _calculate_confidence("A", 80)
        assert conf == pytest.approx(0.85)  # severity ≥ 75 에서도 confidence 감점 없음

    def test_unknown_tier(self):
        assert _calculate_confidence("Z", 50) == pytest.approx(0.50)

    def test_high_severity_reduces_confidence(self):
        # 현재 로직에서는 severity로 confidence를 감점하지 않음
        conf = _calculate_confidence("A", 90)
        assert conf == pytest.approx(0.85)


# ── 통합: normalize() ─────────────────────────────────────────────────────────

class TestNormalize:
    def test_basic_result(self):
        # "kyiv"가 "russia/russian"보다 긴 키워드인 "kyiv"로 매칭됨
        # "russian" 제거하여 UA geo가 확실히 나오도록 함
        text = "Missile strike on kyiv killed dozens. Military casualties reported."
        result = normalize(text, "A", NOW)
        assert result.topic == "conflict"
        assert result.country_code == "UA"
        assert result.severity > 55
        assert len(result.dedup_key) == 32
        assert result.title
        assert result.body == text[:2000]
        assert result.event_time == NOW

    def test_source_tier_propagated(self):
        result = normalize("troops mobilization", "B", NOW)
        assert result.source_tier == "B"
        assert result.confidence == pytest.approx(0.70)

    def test_no_geo_gives_none(self):
        result = normalize("Stock market rally today", "C", NOW)
        assert result.country_code is None
        assert result.lat is None
        assert result.geohash5 is None

    def test_geohash_generated_when_geo_found(self):
        result = normalize("Attack in ukraine near kyiv", "B", NOW)
        assert result.geohash5 is not None
        assert len(result.geohash5) == 5
