"""
스코어링 캘리브레이션 상수 중앙 관리.

앞으로 채널 수나 수집 규모가 크게 바뀌면:
  1. ACTIVE_CHANNELS, EVENTS_PER_CYCLE 업데이트
  2. VOLUME_SATURATION  ≈ EVENTS_PER_CYCLE × 0.10  (상위 10%가 포화점)
  3. ACCEL_BASELINE     ≈ ACTIVE_CHANNELS × 0.5    (채널 절반 수)
  4. 변경 이력 아래에 추가

연계된 상수 → 사용처:
  VOLUME_SATURATION      → tension_calculator._calc_accel_score()
  ACCEL_BASELINE         → tension_calculator._calc_accel_score()
  EVENT_SCORE_MULTIPLIER → tension_calculator._calc_event_score()
  STALE_DECAY            → tension_calculator.calculate_country_tension()
  TENSION_WARMUP_RECORDS → tension_calculator._get_percentile_30d()
  TENSION_WARMUP_FACTOR  → tension_calculator._get_percentile_30d()
  VELOCITY_CAP           → trending_engine._calc_kscore()
  VELOCITY_EXPONENT      → trending_engine._calc_kscore()
  SPIKE_FACTOR           → trending_engine._calc_kscore()
  SPREAD_SATURATION      → trending_engine._calc_kscore()
  KSCORE_MIN             → trending_engine.calculate_global_trending()
  TRENDING_LIMIT         → trending_engine.calculate_global_trending()
  KSCORE_VALID_MINUTES   → trending_engine.calculate_global_trending()

변경 이력:
  v1 (2025-초기): 10채널, ~158건/사이클 기준
    VOLUME_SATURATION=20, ACCEL_BASELINE=5, TRENDING_LIMIT=20
    KSCORE_MIN=0.7, TENSION_WARMUP_RECORDS=5, TENSION_WARMUP_FACTOR=1.0

  v2 (2026-02-25): 37채널, ~1000건/사이클 기준
    VOLUME_SATURATION=100, ACCEL_BASELINE=20, TRENDING_LIMIT=30
    KSCORE_MIN=0.4, TENSION_WARMUP_RECORDS=20, TENSION_WARMUP_FACTOR=0.6

  v3 (2026-02-27): 롤링 베이스라인 정규화 도입
    EVENT_SCORE_MULTIPLIER 의미 변경: raw total이 아닌 정규화된 total에 적용
    BASELINE_WINDOW_DAYS=7, BASELINE_REFERENCE_SCALE=1000
    채널 수 변동에 자동 적응 — 수동 캘리브 불필요

  v4 (2026-02-27): KScore 정규화 및 0-10 스케일 도입
    velocity를 0-1 정규화 (기존: 1.0-6.0 비정규화 → 63% 지배)
    KSCORE_SCALE=10 도입: 최종 KScore = raw(0-1) × 10 → 0-10 범위
    KSCORE_MIN=1.5 (구 0.4에 대응, 새 스케일 기준)
    UI 임계값: 안정(<2) / 주의(2-4) / 경계(4-6) / 심각(6-8) / 극심(8+)

  v5 (2026-03-07): 소스 확장 (37→58채널) 대응
    ACTIVE_CHANNELS=58, SPREAD_SATURATION=12
    소스 58개 체제에서 독립출처 12개 = 상위 20% 수준. 변별력 유지.

  v6 (2026-03-07): Filtered Jaccard + KScore 재조정
    시간감쇠 완화: DECAY_LAMBDA 0.04→0.025 (반감기 17h→28h)
    DECAY_FLOOR 0.15→0.30 (48h 후에도 30% 유지)
    KScore 가중치: severity 지배력 완화 (40%→30%), velocity/spread 강화
    클러스터링: Filtered Jaccard 도입, 윈도우 12h→24h
"""

# ── 환경 파라미터 (모니터링용) ───────────────────────────────────────────────

# 현재 활성 RSS/Telegram/API 채널 수 (v5: 37→58)
ACTIVE_CHANNELS: int = 58

# 15분 사이클당 평균 이벤트 수 (최근 측정 기준)
EVENTS_PER_CYCLE: int = 1000


# ── 긴장도 계산 상수 (tension_calculator.py) ─────────────────────────────────

# 볼륨 포화점: 국가별 총 이벤트 수가 이 값에 도달하면 볼륨=1.0 (100%)
# v1=20 (채널 10개 기준), v2=100 (채널 37개 기준)
# 공식: volume = min(1.0, total_events / VOLUME_SATURATION)
VOLUME_SATURATION: int = 100

# 가속도 베이스라인: prev_count==0일 때 몇 클러스터면 가속도=1.0(최대)
# v1=5, v2=20
# 공식: accel = min(1.0, current_cluster_count / ACCEL_BASELINE)
ACCEL_BASELINE: int = 20

# EventScore 로그 정규화 계수
# v3: 롤링 베이스라인 정규화 후 적용 → total은 BASELINE_REFERENCE_SCALE 기준 상대값
# 공식: min(100.0, EVENT_SCORE_MULTIPLIER * log10(1 + normalized_total))
# normalized=100→50점, normalized=500→68점, normalized=1000→75점, normalized=5000→93점
EVENT_SCORE_MULTIPLIER: float = 25.0

# 롤링 베이스라인 윈도우 (일)
# 전체 국가의 최근 N일 event_score raw total 이동평균을 기준선으로 사용
BASELINE_WINDOW_DAYS: int = 7

# 정규화 기준 스케일
# 글로벌 베이스라인 = 전체 국가 total의 중앙값
# normalized_total = (country_total / baseline) * REFERENCE_SCALE
# REFERENCE_SCALE=1000: 중앙값 수준 국가의 total이 1000이 됨 → 기존 공식과 호환
BASELINE_REFERENCE_SCALE: float = 1000.0

# 오래된 클러스터(24h 초과) EventScore decay 계수
# 공식: event_score = _calc_event_score(recent) + _calc_event_score(stale) * STALE_DECAY
STALE_DECAY: float = 0.5

# 퍼센타일 워밍업: 히스토리 레코드 수가 이 미만이면 워밍업으로 판단
# v1=5, v2=20
TENSION_WARMUP_RECORDS: int = 20

# 워밍업 구간에서 raw_score에 곱하는 할인 계수 (과대 판정 방지)
# v1=1.0 (할인 없음), v2=0.6 (40% 할인)
TENSION_WARMUP_FACTOR: float = 0.6


# ── Conflict-Zone Floor (tension_calculator.py) ─────────────────────────────
# 활발한 분쟁지역의 최소 긴장도 점수.
# 보도 공백 시간에도 0점으로 떨어지는 것을 방지.
# v1: 수작업 정의. 향후 ACLED 90일 이벤트 밀도 기반 자동 산출 전환 예정.
# TODO: Automate floor calculation from ACLED 90-day event density
# - ACLED API에서 국가별 90일 이벤트 수 조회
# - 이벤트 밀도 상위 N개국에 대해 floor 자동 산출
# - 주기적 업데이트 (월 1회 또는 주 1회)
CONFLICT_FLOOR: dict[str, float] = {
    "UA": 55.0,   # 우크라이나: 러시아 전면전
    "PS": 50.0,   # 팔레스타인: 이스라엘-하마스 전쟁
    "SY": 50.0,   # 시리아: 내전 + 공습
    "YE": 45.0,   # 예멘: 후티 반군 + 연합 공습
    "RU": 40.0,   # 러시아: 우크라이나 전쟁 당사국 + 드론 반격
    "MM": 40.0,   # 미얀마: 쿠데타 후 내전
    "SD": 40.0,   # 수단: RSF vs SAF
    "IL": 35.0,   # 이스라엘: 가자·헤즈볼라 분쟁 당사국
    "SO": 35.0,   # 소말리아: 알샤바브
    "AF": 35.0,   # 아프가니스탄: 탈레반 + IS
    "SS": 30.0,   # 남수단: 부족 충돌
    "ET": 30.0,   # 에티오피아: 티그라이
    "LY": 30.0,   # 리비아: 동서 분열
    "BF": 30.0,   # 부르키나파소: 지하디스트
    "IQ": 25.0,   # 이라크: 산발적 IS
    "IR": 25.0,   # 이란: 이스라엘 긴장 + 대리전
    "ML": 25.0,   # 말리: 사헬 분쟁
    "CF": 25.0,   # 중앙아프리카: 반군
    "CD": 25.0,   # 콩고민주공화국: 동부 무장세력
    "NE": 25.0,   # 니제르: 사헬 확산
}


# ── 정보 접근성 보정 (normalizer.py) ────────────────────────────────────────
# RSF Press Freedom Index 기반 (0=자유, 100=통제).
# modifier = 1.0 + (rsf_score / 100) * 0.3
# 자유국(~20): ~1.06, 통제국(~80): ~1.24
# dict에 없는 국가 = 1.0 (보정 없음)
INFORMATION_ACCESSIBILITY: dict[str, float] = {
    "KP": 1.27,   # 북한 (RSF ~90)
    "TM": 1.26,   # 투르크메니스탄 (RSF ~87)
    "ER": 1.25,   # 에리트레아 (RSF ~84)
    "CN": 1.22,   # 중국 (RSF ~75)
    "IR": 1.22,   # 이란 (RSF ~74)
    "MM": 1.21,   # 미얀마 (RSF ~70)
    "SY": 1.21,   # 시리아 (RSF ~70)
    "VN": 1.20,   # 베트남 (RSF ~68)
    "RU": 1.20,   # 러시아 (RSF ~66)
    "BY": 1.19,   # 벨라루스 (RSF ~64)
    "CU": 1.18,   # 쿠바 (RSF ~62)
    "SD": 1.18,   # 수단 (RSF ~60)
    "SA": 1.17,   # 사우디 (RSF ~57)
    "EG": 1.16,   # 이집트 (RSF ~55)
    "AZ": 1.16,   # 아제르바이잔 (RSF ~52)
    "YE": 1.15,   # 예멘 (RSF ~50)
    "AF": 1.15,   # 아프가니스탄 (RSF ~50)
    "PK": 1.14,   # 파키스탄 (RSF ~48)
    "TR": 1.13,   # 튀르키예 (RSF ~45)
    "BD": 1.12,   # 방글라데시 (RSF ~42)
    "VE": 1.12,   # 베네수엘라 (RSF ~40)
    "IQ": 1.11,   # 이라크 (RSF ~38)
    "TH": 1.10,   # 태국 (RSF ~35)
    "IN": 1.10,   # 인도 (RSF ~33)
    "PH": 1.09,   # 필리핀 (RSF ~30)
    "MX": 1.09,   # 멕시코 (RSF ~28)
}


# ── KScore Impact Factors (Phase 1: 10개 주요국 기준) ────────────────────────
# 각 기준국(home_country) 관점에서 이벤트 발생국의 영향도.
# geo=지리 근접(0-1), sec=안보 관련(0-1), eco=경제 연관(0-1)
IMPACT_FACTORS: dict[str, dict[str, dict[str, float]]] = {
    "KR": {  # 한국 기준
        "KP": {"geo": 1.0, "sec": 1.0, "eco": 0.1},
        "KR": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "JP": {"geo": 0.9, "sec": 0.6, "eco": 0.8},
        "CN": {"geo": 0.8, "sec": 0.5, "eco": 0.9},
        "TW": {"geo": 0.6, "sec": 0.6, "eco": 0.7},
        "US": {"geo": 0.3, "sec": 0.8, "eco": 0.7},
        "RU": {"geo": 0.5, "sec": 0.5, "eco": 0.4},
        "SA": {"geo": 0.2, "sec": 0.2, "eco": 0.6},
        "IR": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
        "UA": {"geo": 0.2, "sec": 0.3, "eco": 0.3},
        "DE": {"geo": 0.2, "sec": 0.2, "eco": 0.5},
        "GB": {"geo": 0.2, "sec": 0.3, "eco": 0.4},
        "AU": {"geo": 0.3, "sec": 0.2, "eco": 0.4},
        "VN": {"geo": 0.4, "sec": 0.2, "eco": 0.5},
        "IN": {"geo": 0.3, "sec": 0.2, "eco": 0.4},
        "ID": {"geo": 0.3, "sec": 0.2, "eco": 0.4},
    },
    "US": {  # 미국 기준
        "US": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 0.3, "sec": 0.8, "eco": 0.9},
        "RU": {"geo": 0.3, "sec": 0.9, "eco": 0.4},
        "IR": {"geo": 0.2, "sec": 0.7, "eco": 0.5},
        "KP": {"geo": 0.2, "sec": 0.6, "eco": 0.1},
        "UA": {"geo": 0.2, "sec": 0.7, "eco": 0.3},
        "TW": {"geo": 0.3, "sec": 0.7, "eco": 0.6},
        "MX": {"geo": 0.9, "sec": 0.4, "eco": 0.7},
        "CA": {"geo": 0.9, "sec": 0.3, "eco": 0.8},
        "GB": {"geo": 0.4, "sec": 0.6, "eco": 0.7},
        "IL": {"geo": 0.2, "sec": 0.7, "eco": 0.4},
        "SA": {"geo": 0.2, "sec": 0.5, "eco": 0.7},
        "JP": {"geo": 0.3, "sec": 0.5, "eco": 0.6},
        "DE": {"geo": 0.2, "sec": 0.4, "eco": 0.6},
    },
    "JP": {  # 일본 기준
        "JP": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 0.9, "sec": 0.8, "eco": 0.9},
        "KP": {"geo": 0.8, "sec": 0.9, "eco": 0.1},
        "KR": {"geo": 0.9, "sec": 0.5, "eco": 0.7},
        "TW": {"geo": 0.7, "sec": 0.7, "eco": 0.6},
        "US": {"geo": 0.3, "sec": 0.8, "eco": 0.7},
        "RU": {"geo": 0.6, "sec": 0.6, "eco": 0.3},
        "AU": {"geo": 0.4, "sec": 0.3, "eco": 0.5},
        "IN": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
    },
    "CN": {  # 중국 기준
        "CN": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "TW": {"geo": 0.9, "sec": 1.0, "eco": 0.7},
        "US": {"geo": 0.3, "sec": 0.9, "eco": 0.9},
        "JP": {"geo": 0.8, "sec": 0.6, "eco": 0.7},
        "KR": {"geo": 0.7, "sec": 0.4, "eco": 0.6},
        "IN": {"geo": 0.8, "sec": 0.6, "eco": 0.5},
        "RU": {"geo": 0.7, "sec": 0.5, "eco": 0.5},
        "KP": {"geo": 0.7, "sec": 0.5, "eco": 0.2},
        "AU": {"geo": 0.3, "sec": 0.4, "eco": 0.6},
    },
    "TW": {  # 대만 기준
        "TW": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 1.0, "sec": 1.0, "eco": 0.9},
        "US": {"geo": 0.3, "sec": 0.9, "eco": 0.7},
        "JP": {"geo": 0.7, "sec": 0.5, "eco": 0.7},
        "KR": {"geo": 0.5, "sec": 0.3, "eco": 0.5},
    },
    "DE": {  # 독일 기준
        "DE": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "RU": {"geo": 0.5, "sec": 0.8, "eco": 0.6},
        "UA": {"geo": 0.5, "sec": 0.8, "eco": 0.4},
        "FR": {"geo": 0.9, "sec": 0.4, "eco": 0.8},
        "CN": {"geo": 0.2, "sec": 0.5, "eco": 0.8},
        "US": {"geo": 0.2, "sec": 0.6, "eco": 0.7},
        "TR": {"geo": 0.4, "sec": 0.4, "eco": 0.5},
        "IR": {"geo": 0.2, "sec": 0.5, "eco": 0.4},
    },
    "GB": {  # 영국 기준
        "GB": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "US": {"geo": 0.3, "sec": 0.8, "eco": 0.8},
        "RU": {"geo": 0.4, "sec": 0.8, "eco": 0.4},
        "UA": {"geo": 0.4, "sec": 0.7, "eco": 0.3},
        "FR": {"geo": 0.8, "sec": 0.4, "eco": 0.7},
        "DE": {"geo": 0.6, "sec": 0.4, "eco": 0.7},
        "CN": {"geo": 0.2, "sec": 0.5, "eco": 0.7},
        "IR": {"geo": 0.2, "sec": 0.6, "eco": 0.4},
    },
    "AU": {  # 호주 기준
        "AU": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 0.4, "sec": 0.7, "eco": 0.9},
        "ID": {"geo": 0.8, "sec": 0.4, "eco": 0.5},
        "US": {"geo": 0.3, "sec": 0.7, "eco": 0.6},
        "JP": {"geo": 0.4, "sec": 0.3, "eco": 0.6},
        "NZ": {"geo": 0.9, "sec": 0.2, "eco": 0.5},
        "PH": {"geo": 0.5, "sec": 0.3, "eco": 0.3},
    },
    "IN": {  # 인도 기준
        "IN": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "PK": {"geo": 0.9, "sec": 1.0, "eco": 0.3},
        "CN": {"geo": 0.8, "sec": 0.8, "eco": 0.7},
        "AF": {"geo": 0.7, "sec": 0.6, "eco": 0.2},
        "BD": {"geo": 0.8, "sec": 0.4, "eco": 0.4},
        "LK": {"geo": 0.7, "sec": 0.3, "eco": 0.3},
        "US": {"geo": 0.2, "sec": 0.5, "eco": 0.6},
        "SA": {"geo": 0.3, "sec": 0.3, "eco": 0.7},
        "IR": {"geo": 0.4, "sec": 0.4, "eco": 0.5},
    },
    "BR": {  # 브라질 기준
        "BR": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "VE": {"geo": 0.8, "sec": 0.5, "eco": 0.4},
        "AR": {"geo": 0.8, "sec": 0.3, "eco": 0.6},
        "CO": {"geo": 0.7, "sec": 0.4, "eco": 0.4},
        "US": {"geo": 0.3, "sec": 0.5, "eco": 0.7},
        "CN": {"geo": 0.2, "sec": 0.3, "eco": 0.8},
    },
    "FR": {  # 프랑스 기준
        "FR": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "DE": {"geo": 0.9, "sec": 0.4, "eco": 0.8},
        "GB": {"geo": 0.8, "sec": 0.4, "eco": 0.7},
        "US": {"geo": 0.2, "sec": 0.6, "eco": 0.7},
        "RU": {"geo": 0.3, "sec": 0.7, "eco": 0.5},
        "UA": {"geo": 0.3, "sec": 0.6, "eco": 0.3},
        "CN": {"geo": 0.2, "sec": 0.3, "eco": 0.7},
        "IT": {"geo": 0.8, "sec": 0.3, "eco": 0.6},
        "TR": {"geo": 0.4, "sec": 0.4, "eco": 0.4},
        "IR": {"geo": 0.2, "sec": 0.5, "eco": 0.3},
    },
    "CA": {  # 캐나다 기준
        "CA": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "US": {"geo": 0.9, "sec": 0.3, "eco": 0.8},
        "CN": {"geo": 0.2, "sec": 0.4, "eco": 0.7},
        "GB": {"geo": 0.3, "sec": 0.3, "eco": 0.5},
        "RU": {"geo": 0.5, "sec": 0.5, "eco": 0.3},
        "MX": {"geo": 0.6, "sec": 0.3, "eco": 0.5},
        "FR": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
        "JP": {"geo": 0.2, "sec": 0.3, "eco": 0.4},
        "UA": {"geo": 0.2, "sec": 0.4, "eco": 0.2},
    },
    "SA": {  # 사우디 기준
        "SA": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "IR": {"geo": 0.5, "sec": 0.9, "eco": 0.7},
        "YE": {"geo": 0.9, "sec": 0.8, "eco": 0.3},
        "US": {"geo": 0.2, "sec": 0.7, "eco": 0.8},
        "CN": {"geo": 0.2, "sec": 0.3, "eco": 0.8},
        "IL": {"geo": 0.3, "sec": 0.7, "eco": 0.4},
        "IQ": {"geo": 0.8, "sec": 0.6, "eco": 0.5},
        "AE": {"geo": 0.9, "sec": 0.3, "eco": 0.6},
        "IN": {"geo": 0.3, "sec": 0.3, "eco": 0.6},
        "EG": {"geo": 0.4, "sec": 0.4, "eco": 0.4},
    },
    "IL": {  # 이스라엘 기준
        "IL": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "IR": {"geo": 0.3, "sec": 1.0, "eco": 0.5},
        "SY": {"geo": 0.8, "sec": 0.8, "eco": 0.2},
        "LB": {"geo": 0.9, "sec": 0.8, "eco": 0.2},
        "US": {"geo": 0.2, "sec": 0.9, "eco": 0.6},
        "EG": {"geo": 0.7, "sec": 0.5, "eco": 0.4},
        "JO": {"geo": 0.8, "sec": 0.4, "eco": 0.4},
        "SA": {"geo": 0.3, "sec": 0.5, "eco": 0.4},
        "TR": {"geo": 0.3, "sec": 0.4, "eco": 0.3},
    },
    "RU": {  # 러시아 기준
        "RU": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "UA": {"geo": 0.5, "sec": 1.0, "eco": 0.4},
        "US": {"geo": 0.2, "sec": 0.9, "eco": 0.5},
        "CN": {"geo": 0.6, "sec": 0.5, "eco": 0.7},
        "BY": {"geo": 0.9, "sec": 0.3, "eco": 0.3},
        "KZ": {"geo": 0.8, "sec": 0.3, "eco": 0.4},
        "TR": {"geo": 0.4, "sec": 0.5, "eco": 0.4},
        "DE": {"geo": 0.3, "sec": 0.4, "eco": 0.4},
        "JP": {"geo": 0.5, "sec": 0.5, "eco": 0.3},
        "GB": {"geo": 0.2, "sec": 0.7, "eco": 0.3},
    },
    "TR": {  # 터키 기준
        "TR": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "SY": {"geo": 0.9, "sec": 0.8, "eco": 0.3},
        "IQ": {"geo": 0.8, "sec": 0.6, "eco": 0.4},
        "GR": {"geo": 0.8, "sec": 0.5, "eco": 0.3},
        "RU": {"geo": 0.3, "sec": 0.5, "eco": 0.6},
        "DE": {"geo": 0.3, "sec": 0.3, "eco": 0.6},
        "US": {"geo": 0.2, "sec": 0.5, "eco": 0.5},
        "IR": {"geo": 0.6, "sec": 0.5, "eco": 0.3},
        "AZ": {"geo": 0.6, "sec": 0.3, "eco": 0.3},
        "UA": {"geo": 0.3, "sec": 0.4, "eco": 0.3},
    },
    "TH": {  # 태국 기준
        "TH": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "MM": {"geo": 0.9, "sec": 0.6, "eco": 0.2},
        "CN": {"geo": 0.3, "sec": 0.4, "eco": 0.8},
        "MY": {"geo": 0.8, "sec": 0.3, "eco": 0.4},
        "US": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
        "JP": {"geo": 0.2, "sec": 0.3, "eco": 0.6},
        "KR": {"geo": 0.2, "sec": 0.2, "eco": 0.4},
        "VN": {"geo": 0.7, "sec": 0.3, "eco": 0.3},
        "KH": {"geo": 0.8, "sec": 0.3, "eco": 0.2},
    },
    "VN": {  # 베트남 기준
        "VN": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 0.9, "sec": 0.8, "eco": 0.7},
        "US": {"geo": 0.2, "sec": 0.3, "eco": 0.8},
        "KR": {"geo": 0.3, "sec": 0.3, "eco": 0.6},
        "JP": {"geo": 0.3, "sec": 0.3, "eco": 0.5},
        "TW": {"geo": 0.5, "sec": 0.5, "eco": 0.3},
        "PH": {"geo": 0.5, "sec": 0.4, "eco": 0.3},
        "LA": {"geo": 0.8, "sec": 0.3, "eco": 0.2},
        "KH": {"geo": 0.8, "sec": 0.3, "eco": 0.2},
    },
    "SG": {  # 싱가포르 기준
        "SG": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "MY": {"geo": 0.9, "sec": 0.4, "eco": 0.6},
        "CN": {"geo": 0.3, "sec": 0.4, "eco": 0.8},
        "US": {"geo": 0.2, "sec": 0.5, "eco": 0.7},
        "ID": {"geo": 0.8, "sec": 0.3, "eco": 0.5},
        "IN": {"geo": 0.3, "sec": 0.3, "eco": 0.5},
        "JP": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
        "AU": {"geo": 0.4, "sec": 0.3, "eco": 0.4},
    },
    "AE": {  # UAE 기준
        "AE": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "IR": {"geo": 0.4, "sec": 0.7, "eco": 0.6},
        "SA": {"geo": 0.8, "sec": 0.4, "eco": 0.7},
        "IN": {"geo": 0.3, "sec": 0.3, "eco": 0.7},
        "US": {"geo": 0.2, "sec": 0.5, "eco": 0.6},
        "CN": {"geo": 0.2, "sec": 0.3, "eco": 0.7},
        "PK": {"geo": 0.4, "sec": 0.3, "eco": 0.4},
        "YE": {"geo": 0.6, "sec": 0.6, "eco": 0.3},
        "GB": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
    },
    "MX": {  # 멕시코 기준
        "MX": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "US": {"geo": 0.9, "sec": 0.5, "eco": 0.8},
        "GT": {"geo": 0.8, "sec": 0.4, "eco": 0.3},
        "CN": {"geo": 0.2, "sec": 0.2, "eco": 0.6},
        "CA": {"geo": 0.4, "sec": 0.3, "eco": 0.4},
        "CO": {"geo": 0.5, "sec": 0.4, "eco": 0.3},
        "BR": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
        "DE": {"geo": 0.2, "sec": 0.2, "eco": 0.3},
    },
    "ID": {  # 인도네시아 기준
        "ID": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "MY": {"geo": 0.8, "sec": 0.4, "eco": 0.5},
        "AU": {"geo": 0.6, "sec": 0.4, "eco": 0.5},
        "CN": {"geo": 0.3, "sec": 0.5, "eco": 0.7},
        "SG": {"geo": 0.8, "sec": 0.3, "eco": 0.4},
        "US": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
        "JP": {"geo": 0.2, "sec": 0.3, "eco": 0.5},
        "PH": {"geo": 0.7, "sec": 0.3, "eco": 0.3},
        "IN": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
    },
    "PH": {  # 필리핀 기준
        "PH": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "CN": {"geo": 0.5, "sec": 0.9, "eco": 0.6},
        "US": {"geo": 0.2, "sec": 0.7, "eco": 0.5},
        "JP": {"geo": 0.3, "sec": 0.3, "eco": 0.5},
        "MY": {"geo": 0.6, "sec": 0.3, "eco": 0.3},
        "VN": {"geo": 0.5, "sec": 0.3, "eco": 0.3},
        "ID": {"geo": 0.6, "sec": 0.3, "eco": 0.3},
        "TW": {"geo": 0.5, "sec": 0.4, "eco": 0.3},
    },
    "PL": {  # 폴란드 기준
        "PL": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "UA": {"geo": 0.9, "sec": 0.8, "eco": 0.4},
        "RU": {"geo": 0.4, "sec": 0.9, "eco": 0.3},
        "DE": {"geo": 0.9, "sec": 0.3, "eco": 0.7},
        "BY": {"geo": 0.8, "sec": 0.5, "eco": 0.2},
        "US": {"geo": 0.2, "sec": 0.7, "eco": 0.4},
        "FR": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
        "GB": {"geo": 0.3, "sec": 0.3, "eco": 0.4},
        "CN": {"geo": 0.2, "sec": 0.2, "eco": 0.4},
    },
    "EG": {  # 이집트 기준
        "EG": {"geo": 1.0, "sec": 1.0, "eco": 1.0},
        "IL": {"geo": 0.7, "sec": 0.6, "eco": 0.4},
        "SD": {"geo": 0.8, "sec": 0.5, "eco": 0.2},
        "LY": {"geo": 0.8, "sec": 0.5, "eco": 0.2},
        "SA": {"geo": 0.3, "sec": 0.4, "eco": 0.6},
        "US": {"geo": 0.2, "sec": 0.5, "eco": 0.5},
        "IR": {"geo": 0.3, "sec": 0.4, "eco": 0.3},
        "TR": {"geo": 0.3, "sec": 0.4, "eco": 0.4},
        "ET": {"geo": 0.5, "sec": 0.5, "eco": 0.3},
    },
}

# 지원 기준국 목록 (Phase 1)
SUPPORTED_HOME_COUNTRIES: list[str] = list(IMPACT_FACTORS.keys())

TOPIC_IMPACT_WEIGHTS: dict[str, dict[str, float]] = {
    "conflict":   {"geo": 0.35, "sec": 0.45, "eco": 0.20},
    "terror":     {"geo": 0.40, "sec": 0.40, "eco": 0.20},
    "coup":       {"geo": 0.30, "sec": 0.50, "eco": 0.20},
    "sanctions":  {"geo": 0.20, "sec": 0.25, "eco": 0.55},
    "cyber":      {"geo": 0.20, "sec": 0.30, "eco": 0.50},
    "protest":    {"geo": 0.40, "sec": 0.30, "eco": 0.30},
    "diplomacy":  {"geo": 0.30, "sec": 0.40, "eco": 0.30},
    "maritime":   {"geo": 0.40, "sec": 0.30, "eco": 0.30},
    "disaster":   {"geo": 0.60, "sec": 0.10, "eco": 0.30},
    "health":     {"geo": 0.50, "sec": 0.10, "eco": 0.40},
    "unknown":    {"geo": 0.33, "sec": 0.34, "eco": 0.33},
}

DEFAULT_IMPACT_FACTOR: float = 0.5


# ── KScore 계산 상수 (trending_engine.py) ────────────────────────────────────

# velocity 계산 지수 (k10^VELOCITY_EXPONENT)
# 0.7: 소규모(1~10) 구간 변별력 유지, 대규모에서 cap에 수렴
VELOCITY_EXPONENT: float = 0.7

# velocity 상한 (스파이크 100+이벤트 과도 방지)
# 공식: velocity = min(VELOCITY_CAP, k10^VELOCITY_EXPONENT * spike_factor)
VELOCITY_CAP: float = 6.0

# 스파이크 보너스 배율 (v7: 비활성화, KScore 알림 모델 전환)
SPIKE_FACTOR: float = 1.0

# ── 알림 시스템 플래그 (v7: KScore 기반 알림 모델) ─────────────────────────
USE_SPIKE_DETECTION: bool = False  # 롤백 시 True로 복원
ALERT_SEVERITY_MIN: int = 50      # 알림 트리거 최소 severity
CRITICAL_SEVERITY_MIN: int = 80   # Critical 알림 (상한 무시) 최소 severity
KSCORE_SOCIAL_MIN: float = 5.0    # SNS 자동 포스트 최소 KScore

# spread 포화점: 독립출처 수가 이 값 이상이면 spread=1.0
# 공식: spread = min(1.0, independent_sources / SPREAD_SATURATION)
# v5: 8→12 (58개 소스 체제에서 12개 독립출처 = 상위 20% 수준)
SPREAD_SATURATION: int = 12

# KScore 출력 스케일: raw(0-1) × KSCORE_SCALE → 0-10 범위
# 10점 만점 직관적 스케일. UI 임계값: 안정(<2) / 주의(2-4) / 경계(4-6) / 심각(6-8) / 극심(8+)
KSCORE_SCALE: float = 10.0

# KScore 최소 포함 임계값 (이 미만은 트렌딩 제외)
# v1=0.7, v2=0.4 (0-2.25 스케일), v4=1.5 (0-10 스케일, 구 0.4에 대응)
KSCORE_MIN: float = 1.5

# 트렌딩 상위 N개 저장
# v1=20, v2=30 (더 많은 채널 = 더 많은 이슈)
TRENDING_LIMIT: int = 30

# KScore 시간감쇠: decay = max(DECAY_FLOOR, exp(-DECAY_LAMBDA * age_hours))
# v6: 0.025: 6h→86%, 12h→74%, 24h→55%, 48h→30%(floor)
# (v5: 0.04: 6h→79%, 12h→62%, 24h→38%, 48h→15% — 이벤트 축적 효과를 감쇠가 압도)
DECAY_LAMBDA: float = 0.025
DECAY_FLOOR: float = 0.30

# 트렌딩 키워드 유효 시간 (분)
KSCORE_VALID_HOURS: int = 24
KSCORE_VALID_MINUTES: int = KSCORE_VALID_HOURS * 60


# ── Signal Corroboration (v7) ────────────────────────────────────────────────
# 시그널(열점/단절/교란) 교차검증 시 긴장도 보너스
SIGNAL_BONUS_PER_TYPE: float = 5.0     # 시그널 유형당 tension 보너스
SIGNAL_BONUS_MAX: float = 15.0         # 최대 보너스
SIGNAL_CONFIDENCE_BOOST: float = 0.15  # confidence 최대 상승폭
