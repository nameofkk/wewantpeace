"""
GET /issues  — 지도용 이슈 클러스터 목록.
GET /issues/search — 이슈 클러스터 검색 (title/title_ko ILIKE).
GET /issues/{id} — 이슈 상세 (타임라인 + 소스 이벤트).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import plan_required
from backend.app.core.database import AsyncSessionLocal, get_db
from backend.app.core.limiter import limiter
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


class SearchResultOut(BaseModel):
    id: str
    title: str
    title_ko: Optional[str] = None
    topic: str
    country_code: Optional[str] = None
    severity: int
    event_count: int
    kscore: float
    first_event_at: str
    last_event_at: str
    image_url: Optional[str] = None

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
@limiter.limit("60/minute")
async def list_clusters(
    request: Request,
    response: Response,
    bbox: Optional[str] = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
    topic: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None, description="국가 코드 필터 (예: US, KR)"),
    severity_min: int = Query(1, ge=0, le=100),
    limit: int = Query(200, ge=1, le=2000),
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


@router.get("/search", response_model=list[SearchResultOut])
@limiter.limit("60/minute")
async def search_clusters(
    request: Request,
    q: str = Query(..., min_length=1, description="검색어 (title/title_ko ILIKE)"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    이슈 클러스터 검색.
    - q: 검색 키워드 (영문 title, 한글 title_ko 모두 ILIKE 매칭)
    - limit: 최대 반환 수 (기본 20, 최대 50)
    - offset: 페이지네이션 오프셋
    """
    # ILIKE 와일드카드 이스케이프
    safe_q = q.replace("%", r"\%").replace("_", r"\_")
    pattern = f"%{safe_q}%"
    # country_code 정확 매칭 (2글자 대문자) 또는 title/title_ko ILIKE
    conditions = [
        IssueCluster.title.ilike(pattern),
        IssueCluster.title_ko.ilike(pattern),
    ]
    if len(q) == 2 and q.isalpha():
        conditions.append(IssueCluster.country_code == q.upper())
    stmt = (
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,  # noqa: E712
            or_(*conditions),
        )
        .order_by(
            IssueCluster.severity.desc(),
            IssueCluster.event_count.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    clusters = result.scalars().all()
    return [
        SearchResultOut(
            id=str(c.id),
            title=c.title,
            title_ko=c.title_ko,
            topic=c.topic,
            country_code=c.country_code,
            severity=c.severity,
            event_count=c.event_count,
            kscore=round(c.kscore, 3),
            first_event_at=c.first_event_at.isoformat(),
            last_event_at=c.last_event_at.isoformat(),
            image_url=c.image_url,
        )
        for c in clusters
    ]


class CountryUcdpContextOut(BaseModel):
    total_events: int = 0
    period_start: str | None = None
    period_end: str | None = None
    top_actors: list[str] = []
    total_fatalities_best: int = 0
    total_fatalities_low: int = 0
    total_fatalities_high: int = 0


@router.get("/country/{country_code}/context", response_model=CountryUcdpContextOut)
async def get_country_ucdp_context(
    country_code: str,
    db: AsyncSession = Depends(get_db),
):
    """국가별 UCDP 기반 분쟁 역사 정보."""
    from sqlalchemy import func

    cc = country_code.upper()

    # UCDP 이벤트만 정확히 필터: source_type='api' AND external_id LIKE 'ucdp:%'
    count_result = await db.execute(
        select(func.count(NormalizedEvent.id))
        .join(RawEvent, RawEvent.id == NormalizedEvent.raw_event_id)
        .where(
            NormalizedEvent.country_code == cc,
            RawEvent.source_type == "api",
            RawEvent.external_id.like("ucdp:%"),
        )
    )
    total = count_result.scalar() or 0

    if total == 0:
        return CountryUcdpContextOut()

    # 기간 범위
    range_result = await db.execute(
        select(
            func.min(NormalizedEvent.event_time),
            func.max(NormalizedEvent.event_time),
        )
        .join(RawEvent, RawEvent.id == NormalizedEvent.raw_event_id)
        .where(
            NormalizedEvent.country_code == cc,
            RawEvent.source_type == "api",
            RawEvent.external_id.like("ucdp:%"),
        )
    )
    range_row = range_result.first()
    period_start = range_row[0].isoformat() if range_row and range_row[0] else None
    period_end = range_row[1].isoformat() if range_row and range_row[1] else None

    # top_actors + fatalities: raw_metadata에서 추출
    actors_result = await db.execute(
        select(RawEvent.raw_metadata)
        .join(NormalizedEvent, NormalizedEvent.raw_event_id == RawEvent.id)
        .where(
            NormalizedEvent.country_code == cc,
            RawEvent.source_type == "api",
            RawEvent.external_id.like("ucdp:%"),
        )
        .limit(500)
    )
    actor_counts: dict[str, int] = {}
    total_fat_best = 0
    total_fat_low = 0
    total_fat_high = 0
    for (meta,) in actors_result.all():
        if not meta:
            continue
        for key in ("side_a", "side_b"):
            actor = meta.get(key)
            if actor and isinstance(actor, str) and actor.strip():
                actor_counts[actor.strip()] = actor_counts.get(actor.strip(), 0) + 1
        try:
            total_fat_best += int(meta.get("fatalities_best", 0) or 0)
            total_fat_low += int(meta.get("fatalities_low", 0) or 0)
            total_fat_high += int(meta.get("fatalities_high", 0) or 0)
        except (ValueError, TypeError):
            pass

    top_actors = sorted(actor_counts, key=actor_counts.get, reverse=True)[:3]  # type: ignore[arg-type]

    return CountryUcdpContextOut(
        total_events=total,
        period_start=period_start,
        period_end=period_end,
        top_actors=top_actors,
        total_fatalities_best=total_fat_best,
        total_fatalities_low=total_fat_low,
        total_fatalities_high=total_fat_high,
    )


@router.get("/{cluster_id}", response_model=ClusterDetailOut)
@limiter.limit("60/minute")
async def get_cluster(
    request: Request,
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
    _user=Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
):
    """특정 클러스터에 매칭된 시그널 목록 (교차검증 증거). Pro 이상."""
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
