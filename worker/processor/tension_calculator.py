"""
TensionCalculator: 국가별 긴장도 지수 계산.

공식:
  Raw = 0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover

  EventScore    = 로그 스케일 cumulative severity×confidence 합계 → 0~100
                  (이벤트 많을수록 점수 올라가되 diminishing returns)
  ActivityScore = 볼륨(60%) + 가속도(40%) 혼합 → 0~100
                  볼륨: 이벤트 calibration.VOLUME_SATURATION개면 포화
                  가속도: 급증 시 보너스 (calibration.ACCEL_BASELINE 기준)
  Spillover     = 인접 국가 클러스터 최대 severity / 100

  percentile  = 현재 Raw의 최근 30일 분포 내 위치 → 0~100
  tension_level:
    0 = 안정  (0–24)
    1 = 주의  (25–49)
    2 = 경계  (50–74)
    3 = 위기  (75–100)

결과를 tension_index 테이블에 저장.
모든 튜닝 가능한 상수는 calibration.py에서 관리.
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.tension_index import TensionIndex
from worker.processor.calibration import (
    EVENT_SCORE_MULTIPLIER,
    VOLUME_SATURATION,
    ACCEL_BASELINE,
    STALE_DECAY,
    TENSION_WARMUP_RECORDS,
    TENSION_WARMUP_FACTOR,
)

logger = logging.getLogger(__name__)

# 긴장도 인접 관계 (같은 분쟁 지역 내 spillover)
NEIGHBOR_MAP: dict[str, list[str]] = {
    # 주요국
    "US": ["MX", "CU", "CO"],
    "GB": ["FR", "DE"],
    "FR": ["DE", "GB", "DZ", "ML"],
    "DE": ["FR", "GB"],
    "JP": ["KR", "CN", "KP", "TW"],
    "AU": ["ID", "PH"],
    # 유럽·코카서스
    "UA": ["RU", "BY", "MD"],
    "RU": ["UA", "BY", "GE", "AZ", "KZ"],
    "BY": ["UA", "RU"],
    "MD": ["UA"],
    "RS": ["XK", "BA"],
    "XK": ["RS"],
    "BA": ["RS"],
    "GE": ["RU", "AM", "AZ"],
    "AM": ["GE", "AZ", "IR", "TR"],
    "AZ": ["GE", "AM", "IR", "RU"],
    # 중동
    "PS": ["IL", "LB", "SY", "EG"],
    "IL": ["PS", "LB", "SY", "EG"],
    "IR": ["IQ", "SY", "AF", "PK", "AZ", "TR"],
    "IQ": ["IR", "SY", "SA", "TR"],
    "SY": ["TR", "IQ", "LB", "IL"],
    "LB": ["SY", "IL"],
    "YE": ["SA"],
    "SA": ["YE", "IQ", "EG"],
    "TR": ["SY", "IQ", "GE", "AM", "AZ"],
    "EG": ["IL", "PS", "LY", "SD", "SA"],
    # 동아시아
    "KP": ["KR", "CN"],
    "KR": ["KP"],
    "TW": ["CN"],
    "CN": ["TW", "KP", "MM", "IN", "AF", "KG", "KZ", "TJ"],
    # 동남아
    "MM": ["TH", "IN", "CN"],
    "PH": ["VN", "ID"],
    "VN": ["CN", "PH"],
    "ID": ["PH", "TH"],
    "TH": ["MM", "ID"],
    # 남아시아·중앙아시아
    "PK": ["AF", "IN", "IR"],
    "AF": ["PK", "IR", "TJ", "KG"],
    "IN": ["PK", "CN", "MM", "BD"],
    "BD": ["IN", "MM"],
    "KZ": ["RU", "KG", "TJ"],
    "TJ": ["AF", "KG", "KZ", "CN"],
    "KG": ["KZ", "TJ", "CN"],
    # 아프리카
    "SD": ["ET", "SS", "EG", "LY", "TD", "CF", "ER"],
    "SS": ["SD", "ET", "CD", "CF"],
    "ET": ["SD", "SO", "ER", "SS"],
    "SO": ["ET", "ER"],
    "LY": ["EG", "SD", "TD", "DZ", "TN"],
    "ML": ["BF", "NE", "DZ", "GN"],
    "BF": ["ML", "NE", "GN", "CM"],
    "NE": ["ML", "BF", "NG", "TD"],
    "NG": ["NE", "CM", "TD"],
    "CM": ["NG", "CF", "TD"],
    "CF": ["CM", "CD", "SD", "SS", "TD"],
    "CD": ["CF", "SS", "MZ"],
    "MZ": ["CD"],
    "TD": ["SD", "LY", "NE", "NG", "CM", "CF"],
    "GN": ["ML", "BF"],
    "ER": ["ET", "SD", "SO"],
    "DZ": ["LY", "ML", "TN", "MA"],
    "TN": ["LY", "DZ"],
    "MA": ["DZ"],
    # 아메리카
    "VE": ["CO"],
    "HT": ["CU"],
    "CO": ["VE", "EC"],
    "EC": ["CO"],
    "MX": ["GT"],
    "NI": ["HN", "GT"],
    "CU": ["HT"],
    "GT": ["MX", "HN"],
    "HN": ["GT", "NI"],
}


def _tension_level(percentile: float, raw_score: float = 0.0) -> int:
    """
    퍼센타일과 raw_score 둘 다 고려하여 레벨 결정.

    퍼센타일만 쓰면 '항상 전쟁 중인 나라'(UA)는 30일 모두 높아서
    오늘도 비슷하면 낮은 퍼센타일이 나온다.
    raw_score 절대값 기준도 함께 적용해 높은 쪽을 채택.

    절대값 플로어:
      raw_score < 20  → 최대 안정(0)  — "8점인데 노란색" 방지
      raw_score < 40  → 최대 주의(1)  — 낮은 점수가 경계/위기로 튀는 방지
    """
    # 절대값이 너무 낮으면 퍼센타일이 높아도 상위 레벨 차단
    if raw_score < 20:
        return 0
    if raw_score < 40:
        max_level = 1
    else:
        max_level = 3

    # 퍼센타일 기반 레벨
    p_level = 3 if percentile >= 75 else 2 if percentile >= 50 else 1 if percentile >= 25 else 0
    # raw_score 절대값 기반 레벨 (같은 구간 적용)
    r_level = 3 if raw_score >= 75 else 2 if raw_score >= 50 else 1 if raw_score >= 25 else 0
    return min(max_level, max(p_level, r_level))


def _calc_event_score(clusters: list[IssueCluster]) -> float:
    """event_count 가중 severity×confidence 로그 누적합 → 0~100.

    개선 사항:
    1. 클러스터 내 원본 이벤트 수(event_count)를 log2 스케일로 가중 →
       "우크라이나 전쟁 클러스터 event_count=11" 같은 고밀도 이슈를 정확히 반영
    2. 단순 평균이 아닌 로그 누적합 → 클러스터 많을수록 점수 상승 (단 감쇠)

    예시 (EVENT_SCORE_MULTIPLIER=25):
      UA: 1클러스터 × severity85 × conf0.7 × log2(81) ≈ total 377 → ~64점
      KR: 1클러스터 × severity35 × conf0.6 × log2(2) ≈ total 21 → ~33점
    """
    if not clusters:
        return 0.0
    # event_count 가중: 원본 이벤트가 많을수록 신뢰도 상승 (log2 스케일)
    total = sum(
        c.severity * c.confidence * math.log2(1.0 + c.event_count)
        for c in clusters
    )
    # log10 스케일 정규화 (calibration.EVENT_SCORE_MULTIPLIER)
    return min(100.0, EVENT_SCORE_MULTIPLIER * math.log10(1.0 + total))


def _calc_accel_score(
    current_events: int,
    prev_cluster_count: int,
    current_cluster_count: int,
) -> float:
    """볼륨(60%) + 가속도(40%) 혼합 → 0~1.

    개선 사항:
    - 볼륨: 클러스터 수가 아닌 총 이벤트 수 기준 (event_count 합계)
    - 가속도: 클러스터 수 증감 기준 유지 (prev 클러스터 대비)
    - VOLUME_SATURATION개면 볼륨 포화 (calibration.py 참조)
    - 급증 시 가속도 보너스
    """
    volume = min(1.0, current_events / float(VOLUME_SATURATION))
    if prev_cluster_count == 0:
        accel = min(1.0, current_cluster_count / float(ACCEL_BASELINE))
    else:
        ratio = (current_cluster_count - prev_cluster_count) / max(prev_cluster_count, 1)
        accel = min(1.0, max(0.0, ratio))
    return 0.6 * volume + 0.4 * accel


def _calc_spillover(
    country_code: str,
    all_clusters: dict[str, list[IssueCluster]],
) -> float:
    """인접국 최대 severity → 0~1."""
    neighbors = NEIGHBOR_MAP.get(country_code, [])
    max_sev = 0
    for nb in neighbors:
        for c in all_clusters.get(nb, []):
            if c.severity > max_sev:
                max_sev = c.severity
    return max_sev / 100.0


async def _get_percentile_30d(
    country_code: str,
    raw_score: float,
    db: AsyncSession,
) -> float:
    """최근 30일 raw_score 분포에서 현재 값의 percentile.

    히스토리가 5개 미만이면 raw_score 자체를 반환 (워밍업 기간).
    충분한 히스토리(5개+)가 쌓이면 실제 percentile 계산.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        select(TensionIndex.raw_score)
        .where(
            TensionIndex.country_code == country_code,
            TensionIndex.time >= cutoff,
        )
        .order_by(TensionIndex.time.desc())
        .limit(2880)  # 30일 × 96회/일 최대
    )
    historical = [row[0] for row in result.fetchall()]

    # 워밍업: 히스토리 TENSION_WARMUP_RECORDS개 미만이면 raw_score 할인 적용
    # (히스토리 부족 시 raw_score 그대로 사용 → 과대 판정 방지)
    if len(historical) < TENSION_WARMUP_RECORDS:
        return min(100.0, raw_score * TENSION_WARMUP_FACTOR)

    # 모든 히스토리가 같은 값이면 의미있는 분포 없음 → raw_score 사용
    unique = set(round(h, 1) for h in historical)
    if len(unique) <= 1:
        return min(100.0, raw_score)

    below = sum(1 for h in historical if h < raw_score)
    return round(below / len(historical) * 100.0, 1)


async def calculate_country_tension(
    country_code: str,
    db: AsyncSession,
) -> Optional[dict]:
    """
    단일 국가의 긴장도 계산.
    Returns dict or None.

    윈도우 전략:
    - 1차: 최근 48시간 클러스터 (충분한 데이터 확보, 지속 분쟁국 대응)
    - 가속도: 0~24h vs 24~48h 비교
    - 오래된 클러스터(24h 초과)는 decay_factor=0.5 적용 → EventScore 감쇠
    """
    now = datetime.now(timezone.utc)
    current_cutoff = now - timedelta(hours=48)   # 48시간 윈도우 (지속 분쟁국 대응)
    recent_cutoff  = now - timedelta(hours=24)   # 24h 기준 (가속도 비교용)
    prev_cutoff    = now - timedelta(hours=72)   # 이전 24시간 (48~72h, 가속도 비교용)

    # 현재 48시간 클러스터 (severity >= 30)
    res = await db.execute(
        select(IssueCluster).where(
            IssueCluster.country_code == country_code,
            IssueCluster.last_event_at >= current_cutoff,
            IssueCluster.severity >= 30,
        )
    )
    all_clusters = res.scalars().all()

    # 24h 이내: 최신 (weight 1.0) / 24~48h: 오래된 (weight 0.5 decay)
    recent_clusters = [c for c in all_clusters if c.last_event_at >= recent_cutoff]
    stale_clusters  = [c for c in all_clusters if c.last_event_at < recent_cutoff]

    # Decayed EventScore: 최신 + 오래된×STALE_DECAY
    event_score = (
        _calc_event_score(recent_clusters)
        + _calc_event_score(stale_clusters) * STALE_DECAY
    )
    event_score = min(100.0, event_score)

    # 이전 24시간(48~72h) 클러스터 수 (가속도 계산용)
    res2 = await db.execute(
        select(func.count()).select_from(IssueCluster).where(
            IssueCluster.country_code == country_code,
            IssueCluster.last_event_at >= prev_cutoff,
            IssueCluster.last_event_at < current_cutoff,
            IssueCluster.severity >= 30,
        )
    )
    prev_count = res2.scalar() or 0

    # 볼륨 계산: 최신 클러스터 이벤트 수 기준 (stale은 절반 가중)
    current_total_events = (
        sum(c.event_count for c in recent_clusters)
        + sum(c.event_count for c in stale_clusters) // 2
    )
    accel_score = _calc_accel_score(
        current_events=current_total_events,
        prev_cluster_count=prev_count,
        current_cluster_count=len(all_clusters),
    ) * 100.0

    # spillover (인접국 — 48시간 윈도우)
    neighbor_clusters: dict[str, list[IssueCluster]] = {}
    for nb in NEIGHBOR_MAP.get(country_code, []):
        nb_res = await db.execute(
            select(IssueCluster).where(
                IssueCluster.country_code == nb,
                IssueCluster.last_event_at >= current_cutoff,
            ).limit(5)
        )
        neighbor_clusters[nb] = nb_res.scalars().all()

    spillover = _calc_spillover(country_code, neighbor_clusters) * 100.0

    current_clusters = all_clusters  # 하위 호환 변수명 유지

    raw_score = round(
        0.55 * event_score + 0.35 * accel_score + 0.10 * spillover,
        2,
    )

    percentile = await _get_percentile_30d(country_code, raw_score, db)
    level = _tension_level(percentile, raw_score)

    # TOP5 원인 이슈
    top5 = sorted(current_clusters, key=lambda c: c.severity * c.confidence, reverse=True)[:5]

    entry = TensionIndex(
        time=now,
        country_code=country_code,
        raw_score=raw_score,
        tension_level=level,
        event_score=round(event_score, 2),
        accel_score=round(accel_score, 2),
        spillover_score=round(spillover, 2),
        percentile_30d=percentile,
    )
    db.add(entry)

    return {
        "country_code": country_code,
        "raw_score": raw_score,
        "tension_level": level,
        "percentile_30d": percentile,
        "event_score": round(event_score, 2),
        "accel_score": round(accel_score, 2),
        "spillover_score": round(spillover, 2),
        "top5_clusters": [
            {
                "id": str(c.id),
                "title": c.title,
                "severity": c.severity,
                "confidence": c.confidence,
                "topic": c.topic,
            }
            for c in top5
        ],
    }


# 모니터링 대상 국가 목록 (프론트엔드 ALL_MONITORED_COUNTRIES와 동기화)
MONITORED_COUNTRIES = [
    # 주요국
    "US", "GB", "FR", "DE", "JP", "AU",
    # 유럽·코카서스
    "UA", "RU", "BY", "MD", "RS", "XK", "BA", "GE", "AM", "AZ",
    # 중동
    "PS", "IL", "IR", "IQ", "SY", "LB", "YE", "SA", "TR", "EG",
    # 동아시아
    "KP", "TW", "CN", "KR",
    # 동남아
    "MM", "PH", "VN", "ID", "TH",
    # 남아시아·중앙아시아
    "PK", "AF", "IN", "BD", "KZ", "TJ", "KG",
    # 아프리카
    "SD", "SS", "ET", "SO", "LY", "ML", "BF", "NE", "NG", "CM",
    "CF", "CD", "MZ", "TD", "GN", "ER", "DZ", "TN", "MA",
    # 아메리카
    "VE", "HT", "CO", "EC", "MX", "NI", "CU", "GT", "HN",
]


async def calculate_all_tensions(db: AsyncSession) -> list[dict]:
    """전체 모니터링 국가의 긴장도 계산."""
    results = []
    for code in MONITORED_COUNTRIES:
        result = await calculate_country_tension(code, db)
        if result:
            results.append(result)
    logger.info("긴장도 계산 완료: %d개국", len(results))
    return results
