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
"""

# ── 환경 파라미터 (모니터링용) ───────────────────────────────────────────────

# 현재 활성 RSS/Telegram 채널 수
ACTIVE_CHANNELS: int = 37

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
# 공식: min(100.0, EVENT_SCORE_MULTIPLIER * log10(1 + total))
# total=10→23점, total=100→50점, total=500→84점, total=1000→100점
EVENT_SCORE_MULTIPLIER: float = 25.0

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
SPREAD_SATURATION: int = 5

# KScore 최소 포함 임계값 (이 미만은 트렌딩 제외)
# v1=0.7, v2=0.4 (초기 데이터 부족 시 필터 완화)
KSCORE_MIN: float = 0.4

# 트렌딩 상위 N개 저장
# v1=20, v2=30 (더 많은 채널 = 더 많은 이슈)
TRENDING_LIMIT: int = 30

# 트렌딩 키워드 유효 시간 (분)
KSCORE_VALID_HOURS: int = 24
KSCORE_VALID_MINUTES: int = KSCORE_VALID_HOURS * 60
