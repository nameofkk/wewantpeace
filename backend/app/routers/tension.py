"""
GET /tension/mine              — 관심지역 긴장도 + 원인 TOP5
GET /tension/country/{code}    — 국가별 최신 긴장도 + 히스토리
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, get_db, plan_required
from backend.app.models.user import User
from backend.app.models.tension_index import TensionIndex
from backend.app.models.issue_cluster import IssueCluster

router = APIRouter(prefix="/tension", tags=["tension"])

TENSION_LABELS = {0: "안정", 1: "주의", 2: "경계", 3: "위기"}


# ── Pydantic 스키마 ───────────────────────────────────────────────────────────

class ClusterSummary(BaseModel):
    id: str
    title: str
    title_ko: Optional[str] = None
    severity: int
    confidence: float
    topic: str
    kscore: float = 0.0


class TensionOut(BaseModel):
    country_code: str
    raw_score: float
    tension_level: int
    tension_label: str
    percentile_30d: float
    event_score: float
    accel_score: float
    spillover_score: float
    updated_at: str
    top5_clusters: list[ClusterSummary]


class TensionHistoryPoint(BaseModel):
    time: str
    raw_score: float
    tension_level: int
    percentile_30d: float




# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

async def _latest_tension(country_code: str, db: AsyncSession) -> Optional[TensionIndex]:
    result = await db.execute(
        select(TensionIndex)
        .where(TensionIndex.country_code == country_code)
        .order_by(TensionIndex.time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_top5(country_code: str, db: AsyncSession, min_severity: int = 0) -> list[ClusterSummary]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    result = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.country_code == country_code,
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.severity >= max(min_severity, 1),  # 최소 1 이상 유지
        )
        .order_by(IssueCluster.kscore.desc(), IssueCluster.severity.desc())
        .limit(5)
    )
    clusters = result.scalars().all()
    return [
        ClusterSummary(
            id=str(c.id),
            title=c.title,
            title_ko=c.title_ko,
            severity=c.severity,
            confidence=round(c.confidence, 3),
            topic=c.topic,
            kscore=round(c.kscore, 2),
        )
        for c in clusters
    ]


def _tension_to_out(t: TensionIndex, top5: list[ClusterSummary]) -> TensionOut:
    return TensionOut(
        country_code=t.country_code,
        raw_score=round(t.raw_score, 1),
        tension_level=t.tension_level,
        tension_label=TENSION_LABELS.get(t.tension_level, "알 수 없음"),
        percentile_30d=round(t.percentile_30d or 0.0, 1),
        event_score=round(t.event_score or 0.0, 1),
        accel_score=round(t.accel_score or 0.0, 1),
        spillover_score=round(t.spillover_score or 0.0, 1),
        updated_at=t.time.isoformat(),
        top5_clusters=top5,
    )


# ── 기본 모니터링 국가 ─────────────────────────────────────────────────────────

DEFAULT_COUNTRIES = [
    # 유럽·코카서스
    "UA", "RU", "BY", "MD", "RS", "GE", "AM", "AZ",
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


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("/mine", response_model=list[TensionOut])
async def tension_mine(
    countries: Optional[str] = Query(None, description="쉼표 구분 국가 코드 (예: UA,PS,IL)"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    관심지역 긴장도. countries 파라미터로 필터, 없으면 기본 8개국.
    각 국가별 최신 값 + 원인 TOP5.
    로그인 사용자의 min_severity 설정을 TOP5 클러스터 필터에 적용.
    """
    from backend.app.models.user import UserPreference
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()] if countries else DEFAULT_COUNTRIES

    # 로그인 사용자의 min_severity 조회
    user_min_severity = 0
    if current_user:
        pref_result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == current_user.id)
        )
        pref = pref_result.scalar_one_or_none()
        if pref:
            user_min_severity = pref.min_severity

    # 활성 국가 목록 TensionIndex 최신값 조회 (ORM .in_() 사용 — asyncpg array 타입 문제 회피)
    raw_result = await db.execute(
        select(TensionIndex)
        .where(TensionIndex.country_code.in_(codes))
        .order_by(TensionIndex.country_code, TensionIndex.time.desc())
    )
    all_rows = raw_result.scalars().all()
    tension_map: dict[str, TensionIndex] = {}
    for row in all_rows:
        if row.country_code not in tension_map:
            tension_map[row.country_code] = row

    results = []
    for code in codes:
        t = tension_map.get(code)
        if t is None:
            continue

        top5 = await _get_top5(code, db, min_severity=user_min_severity)
        results.append(_tension_to_out(t, top5))

    return results


@router.get("/country/{country_code}", response_model=TensionOut)
async def tension_country(
    country_code: str,
    db: AsyncSession = Depends(get_db),
):
    """국가별 최신 긴장도 + 원인 TOP5."""
    code = country_code.upper()
    t = await _latest_tension(code, db)

    if t is None:
        raise HTTPException(status_code=404, detail=f"긴장도 데이터 없음: {code}")

    top5 = await _get_top5(code, db)
    return _tension_to_out(t, top5)


_HISTORY_PLAN_DAYS = {"7d": ("free", 7), "30d": ("pro", 30), "90d": ("pro_plus", 90)}


@router.get("/country/{country_code}/history", response_model=list[TensionHistoryPoint])
async def tension_history(
    country_code: str,
    range: str = Query("7d", description="7d / 30d / 90d"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """국가별 긴장도 히스토리 (비로그인/Free: 7일, Pro: 30일, Pro+: 90일)."""
    code = country_code.upper()

    # 플랜 게이팅 (30d는 Pro, 90d는 Pro+ 필요)
    min_plan, days = _HISTORY_PLAN_DAYS.get(range, ("free", 7))
    from backend.app.core.auth import _PLAN_ORDER
    user_level = _PLAN_ORDER.get(current_user.plan.lower(), 0) if current_user else 0
    required_level = _PLAN_ORDER.get(min_plan, 0)
    if user_level < required_level:
        raise HTTPException(
            status_code=403,
            detail={"code": "PLAN_REQUIRED", "required": min_plan, "upgrade_url": "/upgrade"},
        )
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(TensionIndex)
        .where(
            TensionIndex.country_code == code,
            TensionIndex.time >= cutoff,
        )
        .order_by(TensionIndex.time.asc())
    )
    rows = result.scalars().all()

    return [
        TensionHistoryPoint(
            time=r.time.isoformat(),
            raw_score=round(r.raw_score, 1),
            tension_level=r.tension_level,
            percentile_30d=round(r.percentile_30d or 0.0, 1),
        )
        for r in rows
    ]
