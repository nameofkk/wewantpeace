"""
GET /tension/mine              — 관심지역 긴장도 + 원인 TOP5
GET /tension/country/{code}    — 국가별 최신 긴장도 + 히스토리
GET /tension/peek              — 긴장도 레벨 변화 인앱 알림용 폴링
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, get_db, plan_required, require_admin
from backend.app.models.user import User
from backend.app.models.tension_index import TensionIndex
from backend.app.models.issue_cluster import IssueCluster

router = APIRouter(prefix="/tension", tags=["tension"])

TENSION_LABELS = {0: "안정", 1: "주의", 2: "경계", 3: "심각", 4: "극심"}


# ── Pydantic 스키마 ───────────────────────────────────────────────────────────

class ClusterSummary(BaseModel):
    id: str
    title: str
    title_ko: Optional[str] = None
    severity: int
    confidence: float
    topic: str
    kscore: float = 0.0
    event_count: int = 0
    image_url: Optional[str] = None
    country_code: Optional[str] = None


class TensionOut(BaseModel):
    country_code: str
    raw_score: float
    tension_level: int
    tension_label: str
    percentile_30d: float
    event_score: float
    accel_score: float
    spillover_score: float
    convergence_bonus: float = 0.0
    anomaly_z: Optional[float] = None
    delta_24h: Optional[float] = None
    updated_at: str
    top5_clusters: list[ClusterSummary]


class TensionHistoryPoint(BaseModel):
    time: str
    raw_score: float
    tension_level: int
    percentile_30d: float


class TensionPeekItem(BaseModel):
    country_code: str
    tension_level: int
    prev_level: int
    raw_score: float
    change_type: str  # "level_up"




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
            event_count=c.event_count,
            image_url=c.image_url,
            country_code=c.country_code,
        )
        for c in clusters
    ]


async def _get_top5_batch(
    country_codes: list[str], db: AsyncSession, min_severity: int = 0,
) -> dict[str, list[ClusterSummary]]:
    """국가별 top5 클러스터를 1회 배치 쿼리로 조회 (window function)."""
    if not country_codes:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    effective_min = max(min_severity, 1)

    rn_col = sa_func.row_number().over(
        partition_by=IssueCluster.country_code,
        order_by=[IssueCluster.kscore.desc(), IssueCluster.severity.desc()],
    ).label("rn")

    subq = (
        select(
            IssueCluster.id,
            IssueCluster.country_code,
            IssueCluster.title,
            IssueCluster.title_ko,
            IssueCluster.severity,
            IssueCluster.confidence,
            IssueCluster.topic,
            IssueCluster.kscore,
            IssueCluster.event_count,
            IssueCluster.image_url,
            rn_col,
        )
        .where(
            IssueCluster.country_code.in_(country_codes),
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.severity >= effective_min,
        )
        .subquery()
    )

    stmt = (
        select(subq)
        .where(subq.c.rn <= 5)
        .order_by(subq.c.country_code, subq.c.rn)
    )
    result = await db.execute(stmt)
    rows = result.all()

    top5_map: dict[str, list[ClusterSummary]] = {}
    for row in rows:
        cs = ClusterSummary(
            id=str(row.id),
            title=row.title,
            title_ko=row.title_ko,
            severity=row.severity,
            confidence=round(row.confidence, 3),
            topic=row.topic,
            kscore=round(row.kscore, 2),
            event_count=row.event_count,
            image_url=row.image_url,
            country_code=row.country_code,
        )
        top5_map.setdefault(row.country_code, []).append(cs)
    return top5_map


def _tension_to_out(
    t: TensionIndex, top5: list[ClusterSummary], delta_24h: Optional[float] = None,
) -> TensionOut:
    return TensionOut(
        country_code=t.country_code,
        raw_score=round(t.raw_score, 1),
        tension_level=t.tension_level,
        tension_label=TENSION_LABELS.get(t.tension_level, "알 수 없음"),
        percentile_30d=round(t.percentile_30d or 0.0, 1),
        event_score=round(t.event_score or 0.0, 1),
        accel_score=round(t.accel_score or 0.0, 1),
        spillover_score=round(t.spillover_score or 0.0, 1),
        convergence_bonus=round(t.convergence_bonus or 0.0, 2),
        anomaly_z=round(t.anomaly_z, 2) if t.anomaly_z is not None else None,
        delta_24h=delta_24h,
        updated_at=t.time.isoformat(),
        top5_clusters=top5,
    )


# ── 기본 모니터링 국가 ─────────────────────────────────────────────────────────

DEFAULT_COUNTRIES = [
    # 유럽·코카서스
    "UA", "RU", "BY", "MD", "RS", "XK", "BA", "GE", "AM", "AZ",
    "GB", "FR", "DE", "IE", "IS", "LU", "LI", "MC", "MT", "AL",
    "MK", "ME", "SK", "SI", "BG", "LT", "LV", "CY", "AD", "SM",
    "IT", "ES", "PT", "NL", "BE", "SE", "NO", "DK", "CH", "AT",
    "GR", "CZ", "HU", "HR", "FI", "PL", "RO", "EE",
    # 중동
    "PS", "IL", "IR", "IQ", "SY", "LB", "YE", "SA", "TR", "EG",
    "JO", "AE", "QA", "BH", "KW", "OM",
    # 동아시아
    "KP", "KR", "TW", "CN", "JP", "MN",
    # 동남아
    "MM", "PH", "VN", "ID", "TH", "MY", "KH", "LA", "BN", "TL", "SG",
    # 남아시아
    "PK", "AF", "IN", "BD", "LK", "NP", "BT", "MV",
    # 중앙아시아
    "KZ", "TJ", "KG", "UZ", "TM",
    # 아프리카
    "SD", "SS", "ET", "SO", "ER", "LY", "ML", "BF", "NE", "TD",
    "NG", "CM", "CF", "CD", "CG", "MZ", "ZW", "MA", "DZ", "TN",
    "GN", "GW", "SL", "MR", "AO", "BJ", "BW", "BI", "CV", "DJ",
    "GQ", "GA", "GM", "KE", "LS", "LR", "MG", "MW", "MU", "NA",
    "RW", "ST", "SC", "ZA", "SZ", "TG", "TZ", "UG", "ZM", "KM", "CI", "SN", "GH",
    # 남미
    "VE", "HT", "CO", "EC", "PE", "BO", "BR", "GY", "PY", "SR", "UY", "CL", "AR",
    # 중미·카리브
    "MX", "GT", "HN", "SV", "NI", "CU", "CR", "DO", "JM", "PA",
    "TT", "AG", "BB", "BS", "BZ", "DM", "GD", "KN", "LC", "VC",
    # 북미
    "US", "CA",
    # 오세아니아
    "AU", "FJ", "KI", "MH", "FM", "NR", "PW", "PG", "WS", "SB", "TO", "TV", "VU", "NZ",
]


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("/peek", response_model=list[TensionPeekItem])
async def peek_tension(
    since: Optional[str] = Query(None, description="ISO timestamp — 이 시각 이후 알림만 반환"),
):
    """
    긴장도 레벨 변화 인앱 알림용 폴링.
    Redis에서 tension:alert:* 키를 스캔하여 since 이후 레벨 상승 건만 반환.
    최대 3건, 레벨 상승폭 큰 순 정렬.
    """
    import re as _re
    from backend.app.core.redis import get_redis

    since_dt: Optional[datetime] = None
    if since:
        try:
            s = _re.sub(r'\.\d+', '', since.replace("Z", "+00:00"))
            since_dt = datetime.fromisoformat(s)
        except ValueError:
            since_dt = datetime.now(timezone.utc) - timedelta(minutes=5)

    redis = get_redis()
    items: list[TensionPeekItem] = []

    cursor = "0"
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="tension:alert:*", count=100)
        for key in keys:
            val = await redis.get(key)
            if not val:
                continue
            # 형식: "{prev_level}:{new_level}:{raw_score}:{iso_timestamp}"
            parts = val.split(":", 3)
            if len(parts) < 4:
                continue
            prev_level = int(parts[0])
            new_level = int(parts[1])
            raw_score = float(parts[2])
            alert_time_str = parts[3]

            # since 필터
            if since_dt:
                try:
                    alert_time = datetime.fromisoformat(alert_time_str)
                    if alert_time <= since_dt:
                        continue
                except ValueError:
                    continue

            country_code = key.split(":")[-1]
            items.append(TensionPeekItem(
                country_code=country_code,
                tension_level=new_level,
                prev_level=prev_level,
                raw_score=round(raw_score, 1),
                change_type="level_up",
            ))

        if cursor == "0" or cursor == 0:
            break

    # 레벨 상승폭 큰 순 정렬, 최대 3건
    items.sort(key=lambda x: x.tension_level - x.prev_level, reverse=True)
    return items[:3]


@router.get("/mine", response_model=list[TensionOut])
async def tension_mine(
    response: Response,
    countries: Optional[str] = Query(None, description="쉼표 구분 국가 코드 (예: UA,PS,IL)"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    관심지역 긴장도. countries 파라미터로 필터, 없으면 기본 8개국.
    각 국가별 최신 값 + 원인 TOP5.
    로그인 사용자의 min_severity 설정을 TOP5 클러스터 필터에 적용.
    """
    response.headers["Cache-Control"] = "private, max-age=120"
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

    # ── DB에서 국가별 최신 1건만 조회 (DISTINCT ON) ──
    raw_result = await db.execute(
        select(TensionIndex)
        .where(TensionIndex.country_code.in_(codes))
        .distinct(TensionIndex.country_code)
        .order_by(TensionIndex.country_code, TensionIndex.time.desc())
    )
    tension_map: dict[str, TensionIndex] = {
        row.country_code: row for row in raw_result.scalars().all()
    }

    # ── 데이터 없는 국가는 소수(≤5개)일 때만 온더플라이 계산 ──
    missing_codes = [c for c in codes if c not in tension_map]
    if 0 < len(missing_codes) <= 5:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("tension fallback: %d개국 온더플라이 계산", len(missing_codes))
        from backend.app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as calc_db:
                async with calc_db.begin():
                    from worker.processor.tension_calculator import calculate_country_tension
                    for mc in missing_codes:
                        result = await calculate_country_tension(mc, calc_db)
                        if result:
                            _logger.info("tension fallback 완료: %s", mc)
            raw_result2 = await db.execute(
                select(TensionIndex)
                .where(TensionIndex.country_code.in_(missing_codes))
                .distinct(TensionIndex.country_code)
                .order_by(TensionIndex.country_code, TensionIndex.time.desc())
            )
            for row in raw_result2.scalars().all():
                tension_map[row.country_code] = row
        except Exception as e:
            _logger.warning("tension fallback 실패: %s", e)

    # ── 국가별 top5 클러스터 일괄 조회 (1회 배치 쿼리) ──
    active_codes = [c for c in codes if c in tension_map]
    top5_map = await _get_top5_batch(active_codes, db, min_severity=user_min_severity)

    # ── 24h 전 긴장도 배치 조회 (delta_24h 계산용) ──
    delta_map: dict[str, float] = {}
    if active_codes:
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        # 각 국가별 24시간 전 가장 가까운 raw_score 조회
        rn_24h = sa_func.row_number().over(
            partition_by=TensionIndex.country_code,
            order_by=TensionIndex.time.desc(),
        ).label("rn")
        subq_24h = (
            select(TensionIndex.country_code, TensionIndex.raw_score, rn_24h)
            .where(
                TensionIndex.country_code.in_(active_codes),
                TensionIndex.time <= cutoff_24h,
            )
            .subquery()
        )
        prev_result = await db.execute(
            select(subq_24h).where(subq_24h.c.rn == 1)
        )
        for row in prev_result.all():
            delta_map[row.country_code] = row.raw_score

    results = []
    for code in codes:
        t = tension_map.get(code)
        if t is None:
            continue
        prev_score = delta_map.get(code)
        d24h = round(t.raw_score - prev_score, 1) if prev_score is not None else None
        results.append(_tension_to_out(t, top5_map.get(code, []), delta_24h=d24h))

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
    response: Response,
    country_code: str,
    range: str = Query("7d", description="7d / 30d / 90d"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """국가별 긴장도 히스토리 (비로그인/Free: 7일, Pro: 30일, Pro+: 90일)."""
    response.headers["Cache-Control"] = "private, max-age=300"
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


class TensionAllItem(BaseModel):
    country_code: str
    raw_score: float
    tension_level: int


@router.get("/all", response_model=list[TensionAllItem])
async def tension_all(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    전체 국가 최신 긴장도 (히트맵 choropleth용).
    Redis 5분 캐시 적용.
    """
    import json as _json
    response.headers["Cache-Control"] = "public, max-age=300"

    # Redis 캐시 확인
    try:
        from backend.app.core.redis import get_redis
        redis = get_redis()
        cached = await redis.get("tension:all:cache")
        if cached:
            return _json.loads(cached)
    except Exception:
        pass

    # DB에서 국가별 최신 1건만 조회
    raw_result = await db.execute(
        select(TensionIndex)
        .where(TensionIndex.country_code.in_(DEFAULT_COUNTRIES))
        .distinct(TensionIndex.country_code)
        .order_by(TensionIndex.country_code, TensionIndex.time.desc())
    )
    rows = raw_result.scalars().all()
    items = [
        TensionAllItem(
            country_code=r.country_code,
            raw_score=round(r.raw_score, 1),
            tension_level=r.tension_level,
        )
        for r in rows
    ]

    # Redis 캐시 저장 (5분)
    try:
        await redis.set(
            "tension:all:cache",
            _json.dumps([i.model_dump() for i in items]),
            ex=300,
        )
    except Exception:
        pass

    return items


@router.post("/recalculate")
async def tension_recalculate(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """긴장도 즉시 재계산 (admin 전용)."""
    import logging
    _logger = logging.getLogger(__name__)

    from backend.app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as calc_db:
            async with calc_db.begin():
                from worker.processor.tension_calculator import calculate_all_tensions
                results = await calculate_all_tensions(calc_db)
                _logger.info("tension_recalculate 완료: %d개국", len(results))
                return {"status": "ok", "countries": len(results)}
    except Exception as e:
        _logger.error("tension_recalculate 실패: %s", e, exc_info=True)
        raise HTTPException(500, detail="긴장도 재계산 중 오류가 발생했습니다.")
