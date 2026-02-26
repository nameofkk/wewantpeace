"""
GET /trending/global   — KScore 기준 글로벌 트렌딩 20개 (캐시 15분)
GET /trending/mine     — 내 관심지역 트렌딩 (기본 8개국 클러스터 기반 실시간 계산)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import get_redis
from backend.app.core.auth import get_db, get_optional_user
from backend.app.models.user import User, UserPreference
from backend.app.models.trending_keyword import TrendingKeyword
from backend.app.models.issue_cluster import IssueCluster

router = APIRouter(prefix="/trending", tags=["trending"])

_TRENDING_CACHE_KEY = "trending:global:v1"
_TRENDING_CACHE_TTL = 5 * 60  # 5분 (Celery beat 주기와 동기화)


# ── Pydantic 스키마 ───────────────────────────────────────────────────────────

class TrendingItem(BaseModel):
    id: int
    keyword: str
    keyword_ko: Optional[str] = None
    kscore: float
    topic: Optional[str]
    country_codes: list[str]
    cluster_ids: list
    scope: str
    calculated_at: str
    first_event_at: Optional[str] = None
    is_spike: bool = False
    event_count: int = 0
    severity: int = 0
    reason: str = ""
    independent_sources: int = 1


# ── Pydantic 스키마 (추가) ─────────────────────────────────────────────────────

class KScoreHistoryPoint(BaseModel):
    time: str
    kscore: float


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("/global", response_model=list[TrendingItem])
async def global_trending(db: AsyncSession = Depends(get_db)):
    """
    글로벌 트렌딩 상위 20개 반환.
    Redis 15분 캐시 → trending_keywords 테이블 → 실시간 계산 순으로 폴백.
    """
    import json

    # 1. Redis 캐시 확인
    try:
        redis = get_redis()
        cached_json = await redis.get(_TRENDING_CACHE_KEY)
        if cached_json:
            return json.loads(cached_json)
    except Exception:
        pass  # Redis 실패 시 DB 폴백

    now = datetime.now(timezone.utc)

    # 1. trending_keywords 테이블에서 키워드별 최고 KScore 행 조회
    # DISTINCT ON (normalized_kw): 각 키워드의 최고 KScore 행만 선택 → 중복 제거
    from sqlalchemy import text as sa_text
    distinct_result = await db.execute(
        sa_text("""
            SELECT DISTINCT ON (kw.normalized_kw)
                kw.id, kw.keyword, kw.keyword_ko, kw.kscore, kw.topic, kw.country_codes,
                kw.cluster_ids, kw.scope, kw.calculated_at, kw.event_count, kw.severity,
                kw.is_spike, kw.normalized_kw,
                COALESCE(ic.independent_sources, 1) AS independent_sources
            FROM trending_keywords kw
            LEFT JOIN issue_clusters ic ON ic.id = (kw.cluster_ids)[1]
            WHERE kw.scope = 'global'
            ORDER BY kw.normalized_kw, kw.kscore DESC
        """)
    )
    raw_rows = distinct_result.mappings().all()

    if raw_rows:
        # kscore 내림차순 정렬 후 상위 20개
        sorted_rows = sorted(raw_rows, key=lambda r: r["kscore"], reverse=True)[:20]

        # 클러스터 first_event_at 배치 조회
        import uuid as uuid_mod
        all_cids = []
        for r in sorted_rows:
            cids = r["cluster_ids"]
            if cids:
                all_cids.append(cids[0])
        cid_to_first: dict = {}
        if all_cids:
            cr = await db.execute(
                select(IssueCluster.id, IssueCluster.first_event_at).where(
                    IssueCluster.id.in_(all_cids)
                )
            )
            for row in cr.fetchall():
                cid_to_first[str(row[0])] = row[1].isoformat() if row[1] else None

        # raw row → TrendingItem 직접 변환
        out = []
        for r in sorted_rows:
            cid = str(r["cluster_ids"][0]) if r["cluster_ids"] else None
            first_event_at = cid_to_first.get(cid) if cid else None
            out.append(TrendingItem(
                id=r["id"],
                keyword=r["keyword"],
                keyword_ko=r["keyword_ko"],
                kscore=round(float(r["kscore"]), 2),
                topic=r["topic"],
                country_codes=r["country_codes"] or [],
                cluster_ids=[str(u) for u in (r["cluster_ids"] or [])],
                scope=r["scope"],
                calculated_at=r["calculated_at"].isoformat() if hasattr(r["calculated_at"], "isoformat") else str(r["calculated_at"]),
                first_event_at=first_event_at,
                event_count=r["event_count"] or 0,
                severity=r["severity"] or 0,
                is_spike=bool(r["is_spike"]),
                reason=f"KScore {float(r['kscore']):.1f}",
                independent_sources=int(r["independent_sources"] or 1),
            ))

        # Redis 캐시 갱신
        try:
            redis = get_redis()
            await redis.setex(
                _TRENDING_CACHE_KEY,
                _TRENDING_CACHE_TTL,
                json.dumps([item.dict() for item in out]),
            )
        except Exception:
            pass
        return out

    # 2. trending_keywords 없으면 issue_clusters에서 직접 계산 (24시간 윈도우)
    from worker.processor.trending_engine import _calc_kscore
    cutoff24 = now - timedelta(hours=24)

    result2 = await db.execute(
        select(IssueCluster)
        .where(IssueCluster.last_event_at >= cutoff24)
        .order_by(IssueCluster.event_count.desc())
        .limit(200)
    )
    clusters = result2.scalars().all()

    if not clusters:
        return []

    scored = []
    for c in clusters:
        kscore = _calc_kscore(
            event_count=c.event_count,
            is_spike=c.is_spike,
            confidence=c.confidence,
            severity=c.severity,
            independent_sources=c.independent_sources,
            source_tiers=c.source_tiers or [],
        )
        scored.append(TrendingItem(
            id=abs(hash(str(c.id))) % (2 ** 31),
            keyword=c.title,
            keyword_ko=c.title_ko,
            kscore=round(kscore, 2),
            topic=c.topic,
            country_codes=[c.country_code] if c.country_code else [],
            cluster_ids=[str(c.id)],
            scope="global",
            calculated_at=c.last_event_at.isoformat(),
            first_event_at=c.first_event_at.isoformat() if c.first_event_at else None,
            is_spike=c.is_spike,
            event_count=c.event_count,
            severity=c.severity,
            reason=_make_global_reason(c, kscore),
            independent_sources=c.independent_sources,
        ))

    scored.sort(key=lambda x: x.kscore, reverse=True)
    return scored[:20]


_MINE_COUNTRIES = ["UA", "PS", "IL", "IR", "KP", "TW", "SY", "MM"]


@router.get("/mine", response_model=list[TrendingItem])
async def mine_trending(
    countries: Optional[str] = Query(None, description="쉼표 구분 국가 코드 (예: UA,PS,IL)"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    내 관심지역 트렌딩 — countries 파라미터로 필터, 없으면 기본 8개국.
    실시간 KScore 계산. 로그인 사용자의 min_severity 설정 적용.
    """
    from worker.processor.trending_engine import _calc_kscore, KSCORE_MIN

    codes = [c.strip().upper() for c in countries.split(",") if c.strip()] if countries else _MINE_COUNTRIES

    # 로그인 사용자의 min_severity 조회
    user_min_severity = 0
    if current_user:
        pref_result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == current_user.id)
        )
        pref = pref_result.scalar_one_or_none()
        if pref:
            user_min_severity = pref.min_severity

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.country_code.in_(codes),
            IssueCluster.last_event_at >= cutoff,
        )
        .order_by(IssueCluster.event_count.desc())
        .limit(100)
    )
    clusters = result.scalars().all()

    scored = []
    for c in clusters:
        # min_severity 필터: 사용자 설정값 미만 클러스터 제외
        if c.severity < user_min_severity:
            continue
        kscore = _calc_kscore(
            event_count=c.event_count,
            is_spike=c.is_spike,
            confidence=c.confidence,
            severity=c.severity,
            independent_sources=c.independent_sources,
            source_tiers=c.source_tiers or [],
        )
        if kscore < KSCORE_MIN:
            continue
        scored.append(TrendingItem(
            id=abs(hash(str(c.id))) % (2 ** 31),
            keyword=c.title,
            keyword_ko=c.title_ko,
            kscore=round(kscore, 2),
            topic=c.topic,
            country_codes=[c.country_code] if c.country_code else [],
            cluster_ids=[str(c.id)],
            scope="mine",
            calculated_at=c.last_event_at.isoformat(),
            first_event_at=c.first_event_at.isoformat() if c.first_event_at else None,
            is_spike=c.is_spike,
            event_count=c.event_count,
            severity=c.severity,
            reason=_make_mine_reason(c, kscore),
            independent_sources=c.independent_sources,
        ))

    scored.sort(key=lambda x: x.kscore, reverse=True)
    return scored[:20]


def _make_global_reason(cluster: IssueCluster, kscore: float) -> str:
    if cluster.is_spike:
        return f"이벤트 급증 감지 (KScore {kscore:.1f})"
    if cluster.independent_sources >= 3:
        return f"{cluster.independent_sources}개 독립출처 동시 보도 (KScore {kscore:.1f})"
    return f"24시간 내 {cluster.event_count}개 이벤트 (KScore {kscore:.1f})"


def _make_mine_reason(cluster: IssueCluster, kscore: float) -> str:
    if cluster.is_spike:
        return f"관심지역 급증 (KScore {kscore:.1f})"
    return f"{cluster.country_code} — {cluster.event_count}개 이벤트 (KScore {kscore:.1f})"


@router.get("/peek", response_model=list[TrendingItem])
async def peek_trending(
    since: Optional[str] = Query(None, description="ISO timestamp — 이 시각 이후 신규 항목만 반환"),
    min_kscore: float = Query(1.0, ge=0.0, description="최소 KScore 임계값"),
    db: AsyncSession = Depends(get_db),
):
    """
    인앱 알림용 실시간 폴링 엔드포인트.
    since 이후 calculated_at이고 kscore >= min_kscore인 항목 최대 5개 반환.
    Redis 캐시 없음 — 실시간 DB 직접 조회.
    """
    from sqlalchemy import text as sa_text

    try:
        if since:
            import re as _re
            # JavaScript toISOString() 밀리초 포함 형식 처리 (Python < 3.11 호환)
            # "2024-01-15T10:30:00.000Z" → "2024-01-15T10:30:00+00:00"
            s = _re.sub(r'\.\d+', '', since.replace("Z", "+00:00"))
            since_dt = datetime.fromisoformat(s)
        else:
            since_dt = datetime.now(timezone.utc) - timedelta(minutes=2)
    except Exception:
        since_dt = datetime.now(timezone.utc) - timedelta(minutes=2)

    result = await db.execute(
        sa_text("""
            SELECT DISTINCT ON (t.normalized_kw)
                t.id, t.keyword, t.keyword_ko, t.kscore, t.topic, t.country_codes,
                t.cluster_ids, t.scope, t.calculated_at, t.event_count, t.severity, t.is_spike
            FROM trending_keywords t
            WHERE t.scope = 'global'
              AND t.kscore >= :min_kscore
              AND t.calculated_at > :since
              AND NOT EXISTS (
                  SELECT 1 FROM trending_keywords prev
                  WHERE prev.normalized_kw = t.normalized_kw
                    AND prev.scope = 'global'
                    AND prev.calculated_at <= :since
                    AND prev.calculated_at > :since - interval '48 hours'
              )
            ORDER BY t.normalized_kw, t.kscore DESC
        """),
        {"min_kscore": min_kscore, "since": since_dt},
    )
    rows = result.mappings().all()
    sorted_rows = sorted(rows, key=lambda r: float(r["kscore"]), reverse=True)[:5]

    return [
        TrendingItem(
            id=r["id"],
            keyword=r["keyword"],
            keyword_ko=r["keyword_ko"],
            kscore=round(float(r["kscore"]), 2),
            topic=r["topic"],
            country_codes=r["country_codes"] or [],
            cluster_ids=[str(u) for u in (r["cluster_ids"] or [])],
            scope=r["scope"],
            calculated_at=(
                r["calculated_at"].isoformat()
                if hasattr(r["calculated_at"], "isoformat")
                else str(r["calculated_at"])
            ),
            event_count=r["event_count"] or 0,
            severity=r["severity"] or 0,
            is_spike=bool(r["is_spike"]),
            reason=f"KScore {float(r['kscore']):.1f}",
            independent_sources=1,
        )
        for r in sorted_rows
    ]


@router.get("/kscore-history/{cluster_id}", response_model=list[KScoreHistoryPoint])
async def kscore_history(
    cluster_id: str,
    days: int = Query(7, ge=1, le=90),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    클러스터 KScore 시계열 히스토리.
    Free: 최대 7일 / Pro: 30일 / Pro+: 90일
    7일 이하: 시간별, 8일 이상: 일별 집계 반환 (최대 200포인트)
    """
    import uuid as uuid_mod
    from sqlalchemy import text as sa_text

    try:
        cid = uuid_mod.UUID(cluster_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 cluster_id입니다.")

    # 플랜별 최대 조회 기간 제한
    plan = (current_user.plan if current_user else "free") or "free"
    max_days_map = {"free": 7, "pro": 30, "pro_plus": 90}
    days = min(days, max_days_map.get(plan, 7))

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # 조회 기간에 따라 집계 단위 결정 (7일 이하: 시간별, 이상: 일별)
    trunc = "hour" if days <= 7 else "day"

    result = await db.execute(
        sa_text(f"""
            SELECT DISTINCT ON (DATE_TRUNC('{trunc}', calculated_at))
                calculated_at, kscore
            FROM trending_keywords
            WHERE cluster_ids @> ARRAY[CAST(:cid AS uuid)]
              AND calculated_at >= :cutoff
            ORDER BY DATE_TRUNC('{trunc}', calculated_at), calculated_at ASC
            LIMIT 200
        """).bindparams(cid=str(cid), cutoff=cutoff)
    )
    rows = result.fetchall()

    return [
        KScoreHistoryPoint(
            time=row[0].isoformat(),
            kscore=round(float(row[1]), 2),
        )
        for row in rows
    ]


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _kw_to_out(kw: TrendingKeyword, cid_to_first: dict | None = None) -> TrendingItem:
    cid = str(kw.cluster_ids[0]) if kw.cluster_ids else None
    first_event_at = (cid_to_first or {}).get(cid) if cid else None
    return TrendingItem(
        id=kw.id,
        keyword=kw.keyword,
        keyword_ko=kw.keyword_ko,
        kscore=round(kw.kscore, 2),
        topic=kw.topic,
        country_codes=kw.country_codes or [],
        cluster_ids=[str(uuid) for uuid in (kw.cluster_ids or [])],
        scope=kw.scope,
        calculated_at=kw.calculated_at.isoformat(),
        first_event_at=first_event_at,
        event_count=kw.event_count,
        severity=kw.severity,
        is_spike=kw.is_spike,
        reason=f"KScore {kw.kscore:.1f}",
    )
