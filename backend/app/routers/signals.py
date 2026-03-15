"""
Intelligence Signals API.
위성 열점(FIRMS), 인터넷 단절(IODA), GPS 교란, Cloudflare 이상 등
비-뉴스 센서 데이터를 GeoJSON 형식으로 제공.
"""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, plan_required, get_db
from backend.app.core.redis import get_redis
from backend.app.models.signal_point import SignalPoint
from backend.app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])

CACHE_TTL = 300  # 5분


def _to_geojson(signals: list) -> dict:
    """SignalPoint 리스트를 GeoJSON FeatureCollection으로 변환."""
    features = []
    for s in signals:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s.lon, s.lat],
            },
            "properties": {
                "id": str(s.id),
                "signal_type": s.signal_type,
                "intensity": s.intensity,
                "raw_value": s.raw_value,
                "confidence": s.confidence,
                "country_code": s.country_code,
                "observed_at": s.observed_at.isoformat() if s.observed_at else None,
                "metadata": s.extra_data or {},
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/firms")
async def get_firms_signals(
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=72),
):
    """FIRMS 위성 열점 GeoJSON (Pro 전용)."""
    redis = get_redis()
    cache_key = f"signals:firms:{hours}"

    # Redis 캐시 확인
    try:
        cached = await redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    result = await db.execute(
        select(SignalPoint).where(
            SignalPoint.signal_type == "firms_hotspot",
            SignalPoint.observed_at >= cutoff,
            SignalPoint.expires_at > now,
        ).order_by(SignalPoint.observed_at.desc())
    )
    signals = result.scalars().all()
    geojson = _to_geojson(signals)

    try:
        import json
        await redis.set(cache_key, json.dumps(geojson, default=str), ex=CACHE_TTL)
    except Exception:
        pass

    return geojson


@router.get("/outage")
async def get_outage_signals(
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(48, ge=1, le=96),
):
    """인터넷 단절 GeoJSON (Pro 전용)."""
    redis = get_redis()
    cache_key = f"signals:outage:{hours}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    result = await db.execute(
        select(SignalPoint).where(
            SignalPoint.signal_type == "ioda_outage",
            SignalPoint.observed_at >= cutoff,
            SignalPoint.expires_at > now,
        ).order_by(SignalPoint.observed_at.desc())
    )
    signals = result.scalars().all()
    geojson = _to_geojson(signals)

    try:
        import json
        await redis.set(cache_key, json.dumps(geojson, default=str), ex=CACHE_TTL)
    except Exception:
        pass

    return geojson


@router.get("/gps-jam")
async def get_gps_jam_signals(
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=48),
):
    """GPS 교란 지역 GeoJSON (Pro 전용)."""
    redis = get_redis()
    cache_key = f"signals:gps_jam:{hours}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    result = await db.execute(
        select(SignalPoint).where(
            SignalPoint.signal_type == "gps_jam",
            SignalPoint.observed_at >= cutoff,
            SignalPoint.expires_at > now,
        ).order_by(SignalPoint.observed_at.desc())
    )
    signals = result.scalars().all()
    geojson = _to_geojson(signals)

    try:
        import json
        await redis.set(cache_key, json.dumps(geojson, default=str), ex=CACHE_TTL)
    except Exception:
        pass

    return geojson


@router.get("/summary")
async def get_signal_summary(
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """시그널 요약 카운트 (Free 접근 가능, 넛지용)."""
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # 유형별 카운트
    result = await db.execute(
        select(
            SignalPoint.signal_type,
            func.count(SignalPoint.id),
        )
        .where(
            SignalPoint.observed_at >= cutoff_24h,
            SignalPoint.expires_at > now,
        )
        .group_by(SignalPoint.signal_type)
    )
    counts = {row[0]: row[1] for row in result.all()}

    # 최근 업데이트 시각
    latest_result = await db.execute(
        select(func.max(SignalPoint.collected_at)).where(
            SignalPoint.observed_at >= cutoff_24h,
        )
    )
    latest = latest_result.scalar()

    # 영향 국가 수
    country_result = await db.execute(
        select(func.count(func.distinct(SignalPoint.country_code))).where(
            SignalPoint.observed_at >= cutoff_24h,
            SignalPoint.expires_at > now,
            SignalPoint.country_code.isnot(None),
        )
    )
    affected_countries = country_result.scalar() or 0

    return {
        "firms_hotspot": counts.get("firms_hotspot", 0),
        "ioda_outage": counts.get("ioda_outage", 0),
        "cf_anomaly": counts.get("cf_anomaly", 0),
        "gps_jam": counts.get("gps_jam", 0),
        "total": sum(counts.values()),
        "affected_countries": affected_countries,
        "last_updated": latest.isoformat() if latest else None,
    }


@router.get("/matched/{cluster_id}")
async def get_matched_signals(
    cluster_id: str,
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
):
    """특정 클러스터에 매칭된 시그널 GeoJSON (연결선 시각화용)."""
    import uuid as _uuid
    try:
        cid = _uuid.UUID(cluster_id)
    except ValueError:
        return {"type": "FeatureCollection", "features": []}

    result = await db.execute(
        select(SignalPoint).where(
            SignalPoint.matched_cluster_id == cid,
        ).order_by(SignalPoint.observed_at.desc())
    )
    signals = result.scalars().all()
    return _to_geojson(signals)
