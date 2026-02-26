"""
GET /issues  — 지도용 이슈 클러스터 목록.
GET /issues/{id} — 이슈 상세 (타임라인 + 소스 이벤트).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.raw_event import RawEvent
from backend.app.models.source_channel import SourceChannel

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
    return ClusterOut(
        id=str(c.id),
        cluster_key=c.cluster_key,
        topic=c.topic,
        title=c.title,
        title_ko=c.title_ko,
        lat=c.lat,
        lon=c.lon,
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
    # 48시간 윈도우: 오래된 이슈가 지도에 표시되지 않도록 필터링
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    stmt = select(IssueCluster).where(
        IssueCluster.severity >= severity_min,
        IssueCluster.last_event_at >= cutoff,
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
