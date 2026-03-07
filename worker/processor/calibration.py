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


# ── KScore 계산 상수 (trending_engine.py) ────────────────────────────────────

# velocity 계산 지수 (k10^VELOCITY_EXPONENT)
# 0.7: 소규모(1~10) 구간 변별력 유지, 대규모에서 cap에 수렴
VELOCITY_EXPONENT: float = 0.7

# velocity 상한 (스파이크 100+이벤트 과도 방지)
# 공식: velocity = min(VELOCITY_CAP, k10^VELOCITY_EXPONENT * spike_factor)
VELOCITY_CAP: float = 6.0

# 스파이크 보너스 배율
SPIKE_FACTOR: float = 1.5

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
# 0.04: 6h→79%, 12h→62%, 24h→38%, 48h→15%(floor)
DECAY_LAMBDA: float = 0.04
DECAY_FLOOR: float = 0.15

# 트렌딩 키워드 유효 시간 (분)
KSCORE_VALID_HOURS: int = 24
KSCORE_VALID_MINUTES: int = KSCORE_VALID_HOURS * 60
