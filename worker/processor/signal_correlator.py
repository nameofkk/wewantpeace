"""
Signal Correlator — 시그널 ↔ 이슈 클러스터 교차검증 엔진.

5분마다 실행. 미매칭 signal_points를 활성 issue_clusters와
지리(100km) + 시간(24h) 근접성 기반으로 매칭.
매칭 시 클러스터의 independent_sources, confidence, signal_corroboration_count를 보정.
"""
import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 매칭 파라미터
MAX_DISTANCE_KM = 100.0
MAX_TIME_DELTA_H = 24.0
MIN_MATCH_SCORE = 0.3

# 시그널 유형별 가중치
SIGNAL_WEIGHTS: dict[str, float] = {
    "firms_hotspot": 0.3,
    "ioda_outage": 0.5,
    "cf_anomaly": 0.4,
    "gps_jam": 0.6,
}

# spread 포화점 (calibration.py와 동기화)
SPREAD_SATURATION = 12


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리 (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def correlate_signals(db: AsyncSession) -> dict:
    """미매칭 시그널 → 활성 클러스터 매칭."""
    from backend.app.models.signal_point import SignalPoint
    from backend.app.models.issue_cluster import IssueCluster

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)

    # 1. 미매칭 시그널 (최근 48h)
    res = await db.execute(
        select(SignalPoint).where(
            SignalPoint.matched_cluster_id.is_(None),
            SignalPoint.observed_at >= cutoff,
            SignalPoint.expires_at > now,
        )
    )
    unmatched_signals = res.scalars().all()

    if not unmatched_signals:
        return {"matched": 0, "unmatched": 0}

    # 2. 활성 클러스터 (최근 48h)
    res2 = await db.execute(
        select(IssueCluster).where(
            IssueCluster.is_active.is_(True),
            IssueCluster.last_event_at >= cutoff,
        )
    )
    clusters = res2.scalars().all()

    if not clusters:
        return {"matched": 0, "unmatched": len(unmatched_signals)}

    matched = 0
    # 클러스터별 매칭된 시그널 유형 추적
    cluster_updates: dict[str, dict] = {}  # cluster_id -> {types: set, intensities: list}

    for signal in unmatched_signals:
        best_score = 0.0
        best_cluster = None
        best_dist = 0.0
        best_delta = 0.0

        for cluster in clusters:
            if cluster.lat is None or cluster.lon is None:
                continue

            # 거리 계산
            dist = _haversine_km(signal.lat, signal.lon, cluster.lat, cluster.lon)
            if dist > MAX_DISTANCE_KM:
                continue

            # 시간 차이
            time_delta = abs((signal.observed_at - cluster.last_event_at).total_seconds()) / 3600.0
            if time_delta > MAX_TIME_DELTA_H:
                continue

            # 복합 점수
            score = (1.0 - dist / MAX_DISTANCE_KM) * 0.6 + (1.0 - time_delta / MAX_TIME_DELTA_H) * 0.4

            if score > best_score:
                best_score = score
                best_cluster = cluster
                best_dist = dist
                best_delta = time_delta

        if best_score >= MIN_MATCH_SCORE and best_cluster is not None:
            signal.matched_cluster_id = best_cluster.id
            signal.match_distance_km = round(best_dist, 2)
            signal.match_time_delta_h = round(best_delta, 2)
            matched += 1

            # signal_matches 이력 테이블에도 기록
            await db.execute(
                text(
                    "INSERT INTO signal_matches (signal_id, cluster_id, match_score, distance_km, time_delta_h) "
                    "VALUES (:sid, :cid, :score, :dist, :delta) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "sid": str(signal.id),
                    "cid": str(best_cluster.id),
                    "score": round(best_score, 4),
                    "dist": round(best_dist, 2),
                    "delta": round(best_delta, 2),
                },
            )

            cid = str(best_cluster.id)
            if cid not in cluster_updates:
                cluster_updates[cid] = {"types": set(), "intensities": [], "cluster": best_cluster}
            cluster_updates[cid]["types"].add(signal.signal_type)
            cluster_updates[cid]["intensities"].append(
                SIGNAL_WEIGHTS.get(signal.signal_type, 0.3) * signal.intensity
            )

    # 3. 클러스터 보정
    # 새 시그널 교차검증이 추가된 verified 클러스터 → 알림 재발송 후보
    clusters_for_alert: list[tuple] = []  # (cluster_id, signal_corroboration_count)

    for cid, info in cluster_updates.items():
        cluster = info["cluster"]
        types = info["types"]
        intensities = info["intensities"]

        # signal_types 업데이트
        existing_types = set(cluster.signal_types or [])
        new_types = existing_types | types
        newly_added = types - existing_types
        cluster.signal_types = list(new_types)
        cluster.signal_corroboration_count = len(new_types)

        # independent_sources 보정
        new_sources = cluster.independent_sources + len(newly_added)
        cluster.independent_sources = min(SPREAD_SATURATION, new_sources)

        # confidence 보정
        if intensities:
            avg_weighted = sum(intensities) / len(intensities)
            boost = avg_weighted * 0.15
            cluster.confidence = min(1.0, cluster.confidence + boost)

        # 새 시그널 유형이 추가된 verified 클러스터 → 알림 재발송 후보
        if newly_added and getattr(cluster, "is_verified", False):
            clusters_for_alert.append((cid, len(new_types)))

    # 4. 시그널 교차검증으로 보강된 verified 클러스터에 대해 알림 트리거
    if clusters_for_alert:
        try:
            from worker.tasks import push_alert
            for cid, corr_count in clusters_for_alert:
                logger.info(
                    "시그널 교차검증 → verified 알림 트리거: cluster=%s, corroboration=%d",
                    cid, corr_count,
                )
                push_alert.delay(cid, "verified")
        except Exception:
            logger.debug("시그널 교차검증 알림 트리거 실패 (무시)", exc_info=True)

    logger.info(
        "시그널 교차검증 완료: matched=%d, unmatched=%d, clusters_updated=%d, alerts_triggered=%d",
        matched, len(unmatched_signals) - matched, len(cluster_updates), len(clusters_for_alert),
    )

    return {
        "matched": matched,
        "unmatched": len(unmatched_signals) - matched,
        "clusters_updated": len(cluster_updates),
        "alerts_triggered": len(clusters_for_alert),
    }


async def cleanup_expired_signals(db: AsyncSession) -> int:
    """만료된 시그널 삭제."""
    from backend.app.models.signal_point import SignalPoint

    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(SignalPoint).where(
            SignalPoint.expires_at.isnot(None),
            SignalPoint.expires_at < now,
        )
    )
    expired = res.scalars().all()
    count = len(expired)
    for sp in expired:
        await db.delete(sp)

    if count > 0:
        logger.info("만료 시그널 삭제: %d건", count)

    return count
