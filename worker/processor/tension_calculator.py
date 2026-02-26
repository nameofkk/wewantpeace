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
    BASELINE_WINDOW_DAYS,
    BASELINE_REFERENCE_SCALE,
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


def _calc_raw_total(clusters: list[IssueCluster]) -> float:
    """클러스터 목록의 severity×confidence×log2(event_count) 합산 (정규화 전 raw 값)."""
    if not clusters:
        return 0.0
    return sum(
        c.severity * c.confidence * math.log2(1.0 + c.event_count)
        for c in clusters
    )


def _calc_event_score(clusters: list[IssueCluster], baseline: float = 0.0) -> float:
    """event_count 가중 severity×confidence 로그 누적합 → 0~100.

    v3: 롤링 베이스라인 정규화 적용.
    baseline > 0이면 total을 baseline 대비 상대값으로 변환 후 스코어링.
    baseline = 0이면 raw total 그대로 사용 (워밍업 기간).

    정규화: normalized = (total / baseline) * REFERENCE_SCALE
    → 채널 수 변동에 자동 적응. baseline이 커지면 normalized가 줄어듦.
    """
    total = _calc_raw_total(clusters)
    if total == 0.0:
        return 0.0

    # 롤링 베이스라인 정규화
    if baseline > 0:
        normalized = (total / baseline) * BASELINE_REFERENCE_SCALE
    else:
        normalized = total

    return min(100.0, EVENT_SCORE_MULTIPLIER * math.log10(1.0 + normalized))


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
        # 이전 데이터 없음: 현재 클러스터가 있어도 "급증"이라 볼 수 없음
        # 볼륨만 반영, 가속도는 0 (비교 대상 없으므로)
        accel = 0.0
    else:
        ratio = (current_cluster_count - prev_cluster_count) / max(prev_cluster_count, 1)
        accel = min(1.0, max(0.0, ratio))
    return 0.6 * volume + 0.4 * accel


def _calc_spillover(
    country_code: str,
    all_clusters: dict[str, list[IssueCluster]],
) -> float:
    """인접국 severity 가중 평균 × 0.7 → 0~1 (극단값 영향 완화)."""
    neighbors = NEIGHBOR_MAP.get(country_code, [])
    neighbor_max_severities: list[int] = []
    for nb in neighbors:
        nb_clusters = all_clusters.get(nb, [])
        if nb_clusters:
            nb_max = max(c.severity for c in nb_clusters)
            neighbor_max_severities.append(nb_max)
    if not neighbor_max_severities:
        return 0.0
    avg_sev = sum(neighbor_max_severities) / len(neighbor_max_severities)
    return (avg_sev / 100.0) * 0.7


async def _get_percentile_30d(
    country_code: str,
    raw_score: float,
    db: AsyncSession,
) -> float:
    """최근 14일 raw_score 분포에서 현재 값의 percentile.

    히스토리가 5개 미만이면 raw_score 자체를 반환 (워밍업 기간).
    충분한 히스토리(5개+)가 쌓이면 실제 percentile 계산.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    result = await db.execute(
        select(TensionIndex.raw_score)
        .where(
            TensionIndex.country_code == country_code,
            TensionIndex.time >= cutoff,
        )
        .order_by(TensionIndex.time.desc())
        .limit(1344)  # 14일 × 96회/일 최대
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

    # midrank percentile: 동점(±0.5) 절반 반영 → 값이 비슷할 때 0% 방지
    below = sum(1 for h in historical if h < raw_score - 0.5)
    equal = sum(1 for h in historical if abs(h - raw_score) <= 0.5)
    return round((below + 0.5 * equal) / len(historical) * 100.0, 1)


async def calculate_country_tension(
    country_code: str,
    db: AsyncSession,
    baseline: float = 0.0,
) -> Optional[dict]:
    """
    단일 국가의 긴장도 계산.
    Returns dict or None.

    baseline: 글로벌 롤링 베이스라인 (전체 국가 raw total 중앙값의 7일 이동평균).
              0이면 정규화 미적용 (워밍업 기간).

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

    # Decayed EventScore: 최신 + 오래된×STALE_DECAY (롤링 베이스라인 정규화 적용)
    event_score = (
        _calc_event_score(recent_clusters, baseline)
        + _calc_event_score(stale_clusters, baseline) * STALE_DECAY
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

    # ── 레벨 변화 감지 → Redis 알림 기록 ──
    prev_result = await db.execute(
        select(TensionIndex.tension_level)
        .where(TensionIndex.country_code == country_code)
        .order_by(TensionIndex.time.desc())
        .limit(1)
    )
    prev_row = prev_result.first()
    prev_level = prev_row[0] if prev_row else None

    if prev_level is not None and level > prev_level:
        try:
            from backend.app.core.redis import get_redis
            redis = get_redis()
            alert_value = f"{prev_level}:{level}:{raw_score}:{now.isoformat()}"
            await redis.set(
                f"tension:alert:{country_code}",
                alert_value,
                ex=300,  # 5분 TTL
            )
            logger.info(
                "긴장도 레벨 상승 알림: %s %d→%d (%.1f점)",
                country_code, prev_level, level, raw_score,
            )
        except Exception as e:
            logger.warning("긴장도 알림 Redis 저장 실패: %s", e)

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


async def _get_rolling_baseline(db: AsyncSession) -> float:
    """
    글로벌 롤링 베이스라인 계산.

    1단계: 현재 사이클의 전체 국가 raw total 중앙값 산출
    2단계: Redis에서 7일 이동평균 조회/갱신
    3단계: 이동평균 반환 (없으면 현재 중앙값 사용)

    채널 수나 데이터 규모가 바뀌면 7일에 걸쳐 자동 적응.
    """
    import statistics

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)

    # 전체 국가별 raw total 계산
    country_totals: list[float] = []
    for cc in MONITORED_COUNTRIES:
        res = await db.execute(
            select(IssueCluster).where(
                IssueCluster.country_code == cc,
                IssueCluster.last_event_at >= cutoff,
                IssueCluster.severity >= 30,
            )
        )
        clusters = res.scalars().all()
        total = _calc_raw_total(clusters)
        if total > 0:
            country_totals.append(total)

    if not country_totals:
        return 0.0

    current_median = statistics.median(country_totals)

    # Redis 7일 이동평균
    try:
        from backend.app.core.redis import get_redis
        redis = get_redis()
        import json

        key = "tension:baseline:history"
        raw = await redis.get(key)
        history: list[dict] = json.loads(raw) if raw else []

        # 7일 이전 항목 제거
        window_cutoff = (now - timedelta(days=BASELINE_WINDOW_DAYS)).isoformat()
        history = [h for h in history if h["t"] > window_cutoff]

        # 현재 중앙값 추가
        history.append({"t": now.isoformat(), "v": round(current_median, 2)})

        # 저장 (TTL 8일 — 윈도우 7일 + 여유 1일)
        await redis.set(key, json.dumps(history), ex=8 * 86400)

        # 이동평균 계산
        if len(history) >= 2:
            baseline = sum(h["v"] for h in history) / len(history)
        else:
            baseline = current_median

        logger.info(
            "롤링 베이스라인: median=%.1f, 7d_avg=%.1f (히스토리 %d개)",
            current_median, baseline, len(history),
        )
        return baseline

    except Exception as e:
        logger.warning("베이스라인 Redis 실패, 현재 중앙값 사용: %s", e)
        return current_median


async def calculate_all_tensions(db: AsyncSession) -> list[dict]:
    """전체 모니터링 국가의 긴장도 계산 (롤링 베이스라인 정규화 적용)."""
    # 1단계: 글로벌 베이스라인 산출
    baseline = await _get_rolling_baseline(db)

    # 2단계: 각 국가별 긴장도 계산 (베이스라인 전달)
    results = []
    for code in MONITORED_COUNTRIES:
        result = await calculate_country_tension(code, db, baseline)
        if result:
            results.append(result)
    logger.info(
        "긴장도 계산 완료: %d개국 (baseline=%.1f)",
        len(results), baseline,
    )
    return results
