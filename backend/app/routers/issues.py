"""
GET /issues  — 지도용 이슈 클러스터 목록.
GET /issues/{id} — 이슈 상세 (타임라인 + 소스 이벤트).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.raw_event import RawEvent
from backend.app.models.source_channel import SourceChannel

# 국가 코드 → (lat, lon) 기본 좌표 (lat/lon 없는 클러스터에 fallback 제공)
_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "UA": (49.0, 31.0), "RU": (61.0, 105.0), "IL": (31.5, 34.8),
    "PS": (31.5, 34.47), "IR": (32.0, 53.0), "CN": (35.0, 105.0),
    "TW": (23.7, 121.0), "KP": (40.3, 127.5), "KR": (36.5, 127.8),
    "SY": (35.0, 38.0), "MM": (17.0, 96.0), "SD": (15.0, 32.0),
    "ET": (9.0, 38.5), "SO": (5.5, 45.5), "VE": (8.0, -66.0),
    "HT": (19.0, -72.0), "LB": (33.9, 35.5), "IQ": (33.0, 44.0),
    "AF": (33.0, 65.0), "PK": (30.0, 70.0), "IN": (20.0, 77.0),
    "US": (38.0, -97.0), "GB": (54.0, -2.0), "FR": (46.0, 2.0),
    "DE": (51.0, 9.0), "MX": (23.0, -102.0), "AU": (-27.0, 133.0),
    "JP": (35.0, 138.0), "BR": (-14.0, -51.0), "SA": (24.0, 45.0),
    "TR": (39.0, 35.0), "EG": (26.0, 30.0), "NG": (9.0, 8.0),
    "YE": (15.5, 47.5), "LY": (25.0, 17.0), "ML": (17.0, -4.0),
    "BE": (50.85, 4.35), "PH": (12.88, 121.77), "SG": (1.35, 103.82),
    "ID": (-0.79, 113.92), "BD": (23.68, 90.36), "CO": (4.57, -74.3),
    "PE": (-9.19, -75.02), "CL": (-35.68, -71.54), "AR": (-38.42, -63.62),
    "BO": (-16.29, -63.59), "EC": (-1.83, -78.18), "UG": (1.37, 32.29),
    "SN": (14.5, -14.45), "MY": (4.21, 101.97), "EE": (58.6, 25.01),
    "FI": (64.0, 26.0), "PL": (51.92, 19.15), "RO": (45.94, 24.97),
    "IT": (42.83, 12.83), "ES": (40.0, -4.0), "PT": (39.55, -7.86),
    "NL": (52.37, 5.23), "SE": (60.13, 18.64), "NO": (64.5, 17.9),
    "DK": (56.26, 9.5), "CH": (46.82, 8.23), "AT": (47.52, 14.55),
    "GR": (39.07, 21.82), "CZ": (49.82, 15.47), "HU": (47.16, 19.5),
    "RS": (44.02, 21.09), "HR": (45.1, 15.2), "CA": (56.13, -106.35),
    "ZA": (-30.56, 22.94), "KE": (-0.02, 37.91), "GH": (7.95, -1.02),
    "MA": (31.79, -7.09), "DZ": (28.03, 1.66), "TH": (15.87, 100.99),
    "VN": (14.06, 108.28), "NZ": (-40.9, 174.89), "LK": (7.87, 80.77),
    "BY": (53.71, 27.95), "AM": (40.07, 45.04), "AZ": (40.14, 47.58),
    "TJ": (38.86, 71.28), "UZ": (41.38, 64.59), "KH": (12.57, 104.99),
    "ZW": (-20.0, 30.0), "TZ": (-6.37, 34.89), "BI": (-3.37, 29.92),
    "MZ": (-18.67, 35.53), "CM": (7.37, 12.35), "TD": (15.45, 18.73),
    "NE": (17.61, 8.08), "CU": (21.52, -77.78), "NP": (28.39, 84.12),
    "GE": (41.72, 44.79),
}

router = APIRouter(prefix="/issues", tags=["issues"])


# ── Pydantic 응답 스키마 ─────────────────────────────────────────────────────

class ClusterOut(BaseModel):
    id: str
    cluster_key: str
    topic: str
    title: str
    title_ko: Optional[str] = None
    lat: Optional[float]
    lon: Optional[float]
    country_code: Optional[str]
    severity: int
    confidence: float
    event_count: int
    is_spike: bool
    is_verified: bool
    kscore: float
    first_event_at: str
    last_event_at: str

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: str
    title: str
    title_ko: Optional[str] = None
    body: str
    topic: str
    severity: int
    confidence: float
    source_tier: Optional[str]
    source_name: Optional[str] = None   # 출처 채널/매체명
    source_url: Optional[str] = None    # 원문 링크 (RSS: 기사 URL, Telegram: t.me 링크)
    event_time: str
    country_code: Optional[str]
    entity_anchor: Optional[str]

    model_config = {"from_attributes": True}


class ClusterDetailOut(ClusterOut):
    events: list[EventOut]


# ── DB 세션 의존성 ────────────────────────────────────────────────────────────

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _cluster_to_out(c: IssueCluster) -> ClusterOut:
    lat, lon = c.lat, c.lon
    # lat/lon이 없지만 country_code가 있으면 국가 중심 좌표로 fallback
    if (lat is None or lon is None) and c.country_code:
        centroid = _COUNTRY_CENTROIDS.get(c.country_code)
        if centroid:
            lat, lon = centroid
    return ClusterOut(
        id=str(c.id),
        cluster_key=c.cluster_key,
        topic=c.topic,
        title=c.title,
        title_ko=c.title_ko,
        lat=lat,
        lon=lon,
        country_code=c.country_code,
        severity=c.severity,
        confidence=round(c.confidence, 3),
        event_count=c.event_count,
        is_spike=c.is_spike,
        is_verified=c.is_verified,
        kscore=round(c.kscore, 3),
        first_event_at=c.first_event_at.isoformat(),
        last_event_at=c.last_event_at.isoformat(),
    )


def _build_source_url(raw: Optional[RawEvent], sc: Optional[SourceChannel]) -> Optional[str]:
    """raw_event + source_channel → 원문 URL 생성."""
    if not raw:
        return None
    if raw.source_type == "rss":
        link = (raw.raw_metadata or {}).get("link", "")
        return link if link and link.startswith("http") else None
    if raw.source_type == "telegram":
        if sc and sc.username and raw.external_id:
            # external_id: "{chat_id}_{message_id}"
            parts = raw.external_id.rsplit("_", 1)
            message_id = parts[-1] if len(parts) >= 2 else raw.external_id
            return f"https://t.me/{sc.username}/{message_id}"
    return None


def _event_to_out(
    e: NormalizedEvent,
    raw: Optional[RawEvent] = None,
    sc: Optional[SourceChannel] = None,
) -> EventOut:
    return EventOut(
        id=str(e.id),
        title=e.title,
        title_ko=e.title_ko,
        body=e.body or "",
        topic=e.topic,
        severity=e.severity,
        confidence=round(e.confidence, 3),
        source_tier=e.source_tier,
        source_name=sc.display_name if sc else None,
        source_url=_build_source_url(raw, sc),
        event_time=e.event_time.isoformat(),
        country_code=e.country_code,
        entity_anchor=e.entity_anchor,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ClusterOut])
async def list_clusters(
    bbox: Optional[str] = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
    topic: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None, description="국가 코드 필터 (예: US, KR)"),
    severity_min: int = Query(0, ge=0, le=100),
    limit: int = Query(2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """
    지도용 이슈 클러스터 목록.
    - bbox: "min_lon,min_lat,max_lon,max_lat" (선택)
    - topic: conflict/terror/coup/sanctions/cyber/protest/diplomacy/maritime
    - country_code: 국가 코드 필터
    - severity_min: 최소 심각도 (0~100)
    """
    # lat/lon 있거나, country_code가 있으면 fallback 좌표 제공 가능
    stmt = select(IssueCluster).where(
        IssueCluster.severity >= severity_min,
        or_(
            IssueCluster.lat.isnot(None),
            IssueCluster.country_code.isnot(None),
        ),
    ).order_by(IssueCluster.last_event_at.desc()).limit(limit)

    if topic:
        stmt = stmt.where(IssueCluster.topic == topic)

    if country_code:
        stmt = stmt.where(IssueCluster.country_code == country_code.upper())

    if bbox:
        parts = bbox.split(",")
        if len(parts) == 4:
            try:
                min_lon, min_lat, max_lon, max_lat = map(float, parts)
                stmt = stmt.where(
                    IssueCluster.lon >= min_lon,
                    IssueCluster.lon <= max_lon,
                    IssueCluster.lat >= min_lat,
                    IssueCluster.lat <= max_lat,
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format")

    result = await db.execute(stmt)
    clusters = result.scalars().all()
    return [_cluster_to_out(c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterDetailOut)
async def get_cluster(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    """이슈 클러스터 상세 + 연결된 이벤트 타임라인."""
    try:
        uid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster_id")

    result = await db.execute(
        select(IssueCluster).where(IssueCluster.id == uid)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # 연결된 NormalizedEvent + RawEvent + SourceChannel 조회 (출처 URL 확보)
    ev_result = await db.execute(
        select(NormalizedEvent, RawEvent, SourceChannel)
        .join(ClusterEvent, ClusterEvent.event_id == NormalizedEvent.id)
        .outerjoin(RawEvent, RawEvent.id == NormalizedEvent.raw_event_id)
        .outerjoin(SourceChannel, SourceChannel.id == RawEvent.source_channel_id)
        .where(ClusterEvent.cluster_id == uid)
        .order_by(NormalizedEvent.event_time.desc())
        .limit(100)
    )
    rows = ev_result.all()

    detail = ClusterDetailOut(
        **_cluster_to_out(cluster).model_dump(),
        events=[_event_to_out(ne, raw, sc) for ne, raw, sc in rows],
    )
    return detail
