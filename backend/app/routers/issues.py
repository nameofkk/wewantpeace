"""
GET /issues  — 지도용 이슈 클러스터 목록.
GET /issues/{id} — 이슈 상세 (타임라인 + 소스 이벤트).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.raw_event import RawEvent
from backend.app.models.source_channel import SourceChannel
from backend.app.models.cluster_change_log import ClusterChangeLog

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
    is_spike: bool = False  # v7: deprecated, always False
    is_verified: bool
    kscore: float
    independent_sources: int = 0
    source_tiers: list[str] = []
    image_url: Optional[str] = None
    first_event_at: str
    last_event_at: str

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: str
    title: str
    title_ko: Optional[str] = None
    body: str
    body_ko: Optional[str] = None
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


class ChangeLogOut(BaseModel):
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: str
    updated_by: str
    created_at: str


class ClusterDetailOut(ClusterOut):
    events: list[EventOut]
    change_logs: list[ChangeLogOut] = []


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
        is_spike=False,  # v7: deprecated
        is_verified=c.is_verified,
        kscore=round(c.kscore, 3),
        independent_sources=c.independent_sources or 0,
        source_tiers=c.source_tiers or [],
        image_url=c.image_url,
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
        body_ko=getattr(e, "body_ko", None),
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
    response: Response,
    bbox: Optional[str] = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
    topic: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None, description="국가 코드 필터 (예: US, KR)"),
    severity_min: int = Query(1, ge=0, le=100),
    limit: int = Query(2000, ge=1, le=5000),
    sort_by: Optional[str] = Query(None, description="정렬 기준: kscore, severity, latest"),
    db: AsyncSession = Depends(get_db),
):
    """
    지도용 이슈 클러스터 목록.
    - bbox: "min_lon,min_lat,max_lon,max_lat" (선택)
    - topic: conflict/terror/coup/sanctions/cyber/protest/diplomacy/maritime
    - country_code: 국가 코드 필터
    - severity_min: 최소 심각도 (0~100)
    - sort_by: 정렬 기준 (kscore/severity/latest)
    """
    response.headers["Cache-Control"] = "public, max-age=120"
    # 48시간 윈도우: 오래된 이슈가 지도에 표시되지 않도록 필터링
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    order = IssueCluster.last_event_at.desc()
    if sort_by == "kscore":
        order = IssueCluster.kscore.desc()
    elif sort_by == "severity":
        order = IssueCluster.severity.desc()
    stmt = select(IssueCluster).where(
        IssueCluster.is_active == True,  # noqa: E712
        IssueCluster.severity >= severity_min,
        IssueCluster.last_event_at >= cutoff,
    ).order_by(order).limit(limit)

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

    # 변경 로그 조회 (T15)
    log_result = await db.execute(
        select(ClusterChangeLog)
        .where(ClusterChangeLog.cluster_id == uid)
        .order_by(ClusterChangeLog.created_at.desc())
        .limit(20)
    )
    logs = log_result.scalars().all()

    detail = ClusterDetailOut(
        **_cluster_to_out(cluster).model_dump(),
        events=[_event_to_out(ne, raw, sc) for ne, raw, sc in rows],
        change_logs=[
            ChangeLogOut(
                field=log.field,
                old_value=log.old_value,
                new_value=log.new_value,
                reason=log.reason,
                updated_by=log.updated_by,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
    )
    return detail


# ── Signal 관련 엔드포인트 ──────────────────────────────────────────────────


class SignalMatchOut(BaseModel):
    signal_type: str
    intensity: float
    raw_value: float | None = None
    distance_km: float | None = None
    time_delta_h: float | None = None
    country_code: str | None = None
    observed_at: str | None = None
    metadata: dict | None = None


@router.get("/{cluster_id}/signals", response_model=list[SignalMatchOut])
async def get_cluster_signals(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    """특정 클러스터에 매칭된 시그널 목록 (교차검증 증거)."""
    try:
        uid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster_id")

    from backend.app.models.signal_point import SignalPoint

    result = await db.execute(
        select(SignalPoint)
        .where(SignalPoint.matched_cluster_id == uid)
        .order_by(SignalPoint.observed_at.desc())
        .limit(50)
    )
    signals = result.scalars().all()

    return [
        SignalMatchOut(
            signal_type=s.signal_type,
            intensity=s.intensity,
            raw_value=s.raw_value,
            distance_km=s.match_distance_km,
            time_delta_h=s.match_time_delta_h,
            country_code=s.country_code,
            observed_at=s.observed_at.isoformat() if s.observed_at else None,
            metadata=s.extra_data,
        )
        for s in signals
    ]


class HistoricalContextOut(BaseModel):
    total_events: int = 0
    period_start: str | None = None
    period_end: str | None = None
    top_actors: list[str] = []
    recent_fatalities: int = 0
    yearly_trend: list[dict] = []


@router.get("/{cluster_id}/context", response_model=HistoricalContextOut)
async def get_cluster_context(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    """UCDP 기반 역사적 맥락 정보."""
    try:
        uid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster_id")

    # 클러스터의 국가 코드 확인
    cluster_result = await db.execute(
        select(IssueCluster.country_code).where(IssueCluster.id == uid)
    )
    row = cluster_result.first()
    if not row or not row[0]:
        return HistoricalContextOut()

    cc = row[0]

    # UCDP 이벤트 집계 (raw_events에서 external_id가 'ucdp:'로 시작하는 것)
    from sqlalchemy import func, text

    # 해당 국가의 UCDP 이벤트 수
    count_result = await db.execute(
        select(func.count(NormalizedEvent.id))
        .where(
            NormalizedEvent.country_code == cc,
            NormalizedEvent.source_tier == "A",
        )
    )
    total = count_result.scalar() or 0

    if total == 0:
        return HistoricalContextOut()

    # 기간 범위
    range_result = await db.execute(
        select(
            func.min(NormalizedEvent.event_time),
            func.max(NormalizedEvent.event_time),
        )
        .where(
            NormalizedEvent.country_code == cc,
            NormalizedEvent.source_tier == "A",
        )
    )
    range_row = range_result.first()
    period_start = range_row[0].isoformat() if range_row and range_row[0] else None
    period_end = range_row[1].isoformat() if range_row and range_row[1] else None

    return HistoricalContextOut(
        total_events=total,
        period_start=period_start,
        period_end=period_end,
    )
