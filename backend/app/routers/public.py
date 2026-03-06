"""
/public/* 인증 불필요 공개 API
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from backend.app.core.auth import get_db
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
