"""
/public/* 인증 불필요 공개 API
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from backend.app.core.auth import get_db
from backend.app.core.limiter import limiter
from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.tension_index import TensionIndex

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/weekly-summary")
async def weekly_summary(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """최근 7일 주간 요약 — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=1800, stale-while-revalidate=3600"

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # TOP 10 이슈 클러스터
    top_clusters_q = await db.execute(
        select(
            IssueCluster.id,
            IssueCluster.title,
            IssueCluster.title_ko,
            IssueCluster.severity,
            IssueCluster.kscore,
            IssueCluster.event_count,
            IssueCluster.country_code,
            IssueCluster.topic,
        )
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(10)
    )
    top_issues = [
        {
            "id": str(row.id),
            "title": row.title,
            "title_ko": row.title_ko,
            "severity": row.severity,
            "kscore": round(row.kscore, 2),
            "event_count": row.event_count,
            "country_code": row.country_code,
            "topic": row.topic,
        }
        for row in top_clusters_q.all()
    ]

    # TOP 10 긴장도 국가 (최신 값, raw_score DESC)
    latest_tension_subq = (
        select(
            TensionIndex.country_code,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            func.row_number()
            .over(
                partition_by=TensionIndex.country_code,
                order_by=TensionIndex.time.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )
    tension_q = await db.execute(
        select(
            latest_tension_subq.c.country_code,
            latest_tension_subq.c.raw_score,
            latest_tension_subq.c.tension_level,
        )
        .where(latest_tension_subq.c.rn == 1)
        .order_by(latest_tension_subq.c.raw_score.desc())
        .limit(10)
    )
    top_tension = [
        {
            "country_code": row.country_code,
            "raw_score": round(row.raw_score, 1),
            "tension_level": row.tension_level,
        }
        for row in tension_q.all()
    ]

    # 통계 — 이번 주
    total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff)
    )).scalar() or 0

    new_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster)
        .where(IssueCluster.first_event_at >= cutoff)
    )).scalar() or 0

    crisis_countries_q = await db.execute(
        select(latest_tension_subq.c.country_code)
        .where(latest_tension_subq.c.rn == 1, latest_tension_subq.c.raw_score >= 70)
    )
    crisis_countries = len(crisis_countries_q.all())

    # 통계 — 전주 (WoW 비교용)
    prev_cutoff = cutoff - timedelta(days=7)
    prev_total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= prev_cutoff, NormalizedEvent.created_at < cutoff)
    )).scalar() or 0

    prev_new_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster)
        .where(IssueCluster.first_event_at >= prev_cutoff, IssueCluster.first_event_at < cutoff)
    )).scalar() or 0

    return {
        "period": {"start": cutoff.isoformat(), "end": now.isoformat()},
        "top_issues": top_issues,
        "top_tension": top_tension,
        "stats": {
            "total_events": total_events,
            "new_clusters": new_clusters,
            "crisis_countries": crisis_countries,
        },
        "prev_stats": {
            "total_events": prev_total_events,
            "new_clusters": prev_new_clusters,
        },
    }


# ---------------------------------------------------------------------------
# 1) GET /public/tension/all — 전체 국가 긴장도 (최신 값)
# ---------------------------------------------------------------------------
@router.get("/tension/all")
@limiter.limit("60/minute")
async def tension_all(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """전체 국가별 최신 긴장도 — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"

    # 각 국가별 최신 레코드 1건
    latest_subq = (
        select(
            TensionIndex.country_code,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            TensionIndex.event_score,
            TensionIndex.accel_score,
            TensionIndex.spillover_score,
            TensionIndex.percentile_30d,
            TensionIndex.time,
            func.row_number()
            .over(
                partition_by=TensionIndex.country_code,
                order_by=TensionIndex.time.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )

    rows = (await db.execute(
        select(
            latest_subq.c.country_code,
            latest_subq.c.raw_score,
            latest_subq.c.tension_level,
            latest_subq.c.event_score,
            latest_subq.c.accel_score,
            latest_subq.c.spillover_score,
            latest_subq.c.percentile_30d,
            latest_subq.c.time,
        )
        .where(latest_subq.c.rn == 1)
        .order_by(latest_subq.c.raw_score.desc())
    )).all()

    return {
        "count": len(rows),
        "data": [
            {
                "country_code": r.country_code,
                "raw_score": round(r.raw_score, 2),
                "tension_level": r.tension_level,
                "event_score": round(r.event_score, 2) if r.event_score else 0,
                "accel_score": round(r.accel_score, 2) if r.accel_score else 0,
                "spillover_score": round(r.spillover_score, 2) if r.spillover_score else 0,
                "percentile_30d": round(r.percentile_30d, 2) if r.percentile_30d else 0,
                "updated_at": r.time.isoformat(),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 2) GET /public/tension/{country_code} — 개별 국가 긴장도 + 히스토리
# ---------------------------------------------------------------------------
@router.get("/tension/{country_code}")
@limiter.limit("60/minute")
async def tension_by_country(
    country_code: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """개별 국가 긴장도 최신 값 + 최근 30일 히스토리 — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"

    cc = country_code.upper()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # 최근 30일 히스토리 (시간순)
    history_q = await db.execute(
        select(
            TensionIndex.time,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            TensionIndex.event_score,
            TensionIndex.accel_score,
            TensionIndex.spillover_score,
            TensionIndex.percentile_30d,
        )
        .where(TensionIndex.country_code == cc, TensionIndex.time >= cutoff)
        .order_by(TensionIndex.time.asc())
    )
    history_rows = history_q.all()

    if not history_rows:
        return {"country_code": cc, "latest": None, "history": []}

    latest = history_rows[-1]

    return {
        "country_code": cc,
        "latest": {
            "raw_score": round(latest.raw_score, 2),
            "tension_level": latest.tension_level,
            "event_score": round(latest.event_score, 2) if latest.event_score else 0,
            "accel_score": round(latest.accel_score, 2) if latest.accel_score else 0,
            "spillover_score": round(latest.spillover_score, 2) if latest.spillover_score else 0,
            "percentile_30d": round(latest.percentile_30d, 2) if latest.percentile_30d else 0,
            "updated_at": latest.time.isoformat(),
        },
        "history": [
            {
                "time": r.time.isoformat(),
                "raw_score": round(r.raw_score, 2),
                "tension_level": r.tension_level,
            }
            for r in history_rows
        ],
    }


# ---------------------------------------------------------------------------
# 3) GET /public/trending/top — 상위 20개 트렌딩 이슈
# ---------------------------------------------------------------------------
@router.get("/trending/top")
@limiter.limit("60/minute")
async def trending_top(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """상위 20개 트렌딩 이슈 (kscore 내림차순) — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"

    rows_q = await db.execute(
        select(
            IssueCluster.id,
            IssueCluster.title,
            IssueCluster.title_ko,
            IssueCluster.severity,
            IssueCluster.kscore,
            IssueCluster.event_count,
            IssueCluster.country_code,
            IssueCluster.topic,
            IssueCluster.lat,
            IssueCluster.lon,
            IssueCluster.is_spike,
            IssueCluster.last_event_at,
            IssueCluster.image_url,
        )
        .where(IssueCluster.is_active.is_(True), IssueCluster.severity > 0)
        .order_by(IssueCluster.kscore.desc())
        .limit(20)
    )
    rows = rows_q.all()

    return {
        "count": len(rows),
        "data": [
            {
                "id": str(r.id),
                "title": r.title,
                "title_ko": r.title_ko,
                "severity": r.severity,
                "kscore": round(r.kscore, 2),
                "event_count": r.event_count,
                "country_code": r.country_code,
                "topic": r.topic,
                "lat": r.lat,
                "lon": r.lon,
                "is_spike": r.is_spike,
                "last_event_at": r.last_event_at.isoformat() if r.last_event_at else None,
                "image_url": r.image_url,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 4) GET /public/countries — 데이터가 존재하는 국가 목록
# ---------------------------------------------------------------------------
@router.get("/countries")
@limiter.limit("60/minute")
async def countries_list(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """데이터가 존재하는 국가 코드 목록 — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=7200"

    # tension_index와 issue_clusters에서 고유 국가 코드 수집
    tension_cc = (await db.execute(
        select(distinct(TensionIndex.country_code))
    )).scalars().all()

    cluster_cc = (await db.execute(
        select(distinct(IssueCluster.country_code))
        .where(IssueCluster.is_active.is_(True))
    )).scalars().all()

    all_codes = sorted(set(tension_cc) | set(cluster_cc))

    return {
        "count": len(all_codes),
        "data": all_codes,
    }


# ---------------------------------------------------------------------------
# 5) GET /public/stats — 플랫폼 통계
# ---------------------------------------------------------------------------
@router.get("/stats")
@limiter.limit("60/minute")
async def platform_stats(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """플랫폼 전체 통계 — 인증 불필요."""
    response.headers["Cache-Control"] = "public, max-age=600, stale-while-revalidate=1200"

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    # 전체 이벤트 수
    total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
    )).scalar() or 0

    # 최근 24시간 이벤트 수
    events_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h)
    )).scalar() or 0

    # 활성 클러스터 수
    active_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster)
        .where(IssueCluster.is_active.is_(True), IssueCluster.severity > 0)
    )).scalar() or 0

    # 모니터링 국가 수
    monitored_countries = (await db.execute(
        select(func.count(distinct(TensionIndex.country_code)))
    )).scalar() or 0

    # 최근 7일 새 클러스터 수
    new_clusters_7d = (await db.execute(
        select(func.count()).select_from(IssueCluster)
        .where(IssueCluster.first_event_at >= cutoff_7d)
    )).scalar() or 0

    return {
        "total_events": total_events,
        "events_24h": events_24h,
        "active_clusters": active_clusters,
        "monitored_countries": monitored_countries,
        "new_clusters_7d": new_clusters_7d,
        "updated_at": now.isoformat(),
    }
