"""
Impact Dashboard endpoints — Phase 2-5

Phase 2: Impact Brief (Pro) — AI-powered impact analysis per cluster
Phase 3: Sector Impact Analysis (Pro+) — sector-level exposure analysis
Phase 4: Weekly Report (Pro+) — weekly impact summary
Phase 5: Behavior Personalization — event tracking + recommendations
"""

import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, plan_required, get_db
from backend.app.core.redis import get_redis
from backend.app.models.user import User
from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.normalized_event import NormalizedEvent

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/impact", tags=["impact"])

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")


# ── Phase 2: Impact Brief ──────────────────────────────────────────────────

class ImpactBriefOut(BaseModel):
    cluster_id: str
    title: str
    title_ko: Optional[str] = None
    economy: str
    trade: str
    travel: str
    summary: str
    score: int = Field(ge=0, le=100, description="Overall impact score 0-100")
    data_sources: list[str] = []
    generated_at: str
    cached: bool = False


def _brief_cache_key(cluster_id: str, home_country: str) -> str:
    return f"impact:brief:{cluster_id}:{home_country}"


async def _generate_impact_brief(
    cluster: IssueCluster,
    home_country: str,
    lang: str,
    db: AsyncSession,
) -> dict:
    """AI를 사용하여 클러스터의 경제/무역/여행 영향 분석을 생성합니다."""

    # 클러스터의 최근 이벤트 수집 (최대 10개)
    from backend.app.models.issue_cluster import ClusterEvent
    event_ids_q = await db.execute(
        select(ClusterEvent.event_id)
        .where(ClusterEvent.cluster_id == cluster.id)
        .limit(10)
    )
    event_ids = [r[0] for r in event_ids_q.fetchall()]

    event_titles = []
    if event_ids:
        events_q = await db.execute(
            select(NormalizedEvent.title, NormalizedEvent.body)
            .where(NormalizedEvent.id.in_(event_ids))
        )
        for row in events_q.fetchall():
            event_titles.append(row[0] or "")

    events_text = "\n".join(f"- {t}" for t in event_titles[:10])
    cluster_title = cluster.title or "Unknown"
    cluster_topic = cluster.topic or "unknown"
    country_code = cluster.country_code or "Unknown"

    if OPENAI_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)

            system_prompt = """You are an expert geopolitical risk analyst.
Analyze how a global conflict/crisis affects a specific country across three dimensions:
1. Economy: GDP, inflation, supply chain, energy prices
2. Trade: imports/exports, sanctions, shipping routes
3. Travel: safety advisories, flight disruptions, visa restrictions

IMPORTANT RULES:
- NEVER give investment advice or mention stocks/securities
- Use phrases like "potential impact" not "will cause"
- Always note this is an AI estimate based on public data
- Cite data sources (World Bank, UN, OECD, etc.)
- Keep each section 2-3 sentences max
- Provide an overall impact score 0-100
- Respond in the requested language"""

            user_prompt = f"""Analyze impact on {home_country}:

Crisis: {cluster_title}
Topic: {cluster_topic}
Affected region: {country_code}
Severity: {cluster.severity}/100

Recent events:
{events_text}

Respond in {"Korean" if lang == "ko" else "English"} as JSON:
{{"economy": "...", "trade": "...", "travel": "...", "summary": "one-line summary", "score": 0-100, "data_sources": ["World Bank", ...]}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800,
            )

            result = json.loads(response.choices[0].message.content)
            return {
                "economy": result.get("economy", ""),
                "trade": result.get("trade", ""),
                "travel": result.get("travel", ""),
                "summary": result.get("summary", ""),
                "score": min(100, max(0, int(result.get("score", 50)))),
                "data_sources": result.get("data_sources", ["World Bank", "UN OCHA"]),
            }
        except Exception as e:
            logger.error("impact_brief_ai_error", error=str(e), cluster_id=str(cluster.id))

    # Fallback: 규칙 기반 간단 분석
    severity = cluster.severity or 0
    score = min(100, int(severity * 0.8))
    if lang == "ko":
        return {
            "economy": f"해당 분쟁은 {country_code} 지역의 경제 안정성에 영향을 줄 수 있으며, 에너지 및 원자재 가격 변동 가능성이 있습니다.",
            "trade": f"관련 지역과의 교역에 잠재적 영향이 예상되며, 공급망 차질 가능성을 모니터링해야 합니다.",
            "travel": f"해당 지역 여행 시 안전 주의가 필요하며, 항공편 변동 가능성이 있습니다.",
            "summary": f"심각도 {severity}/100 수준의 분쟁으로, 경제·무역·여행 측면에서 주의가 필요합니다.",
            "score": score,
            "data_sources": ["World Bank", "UN OCHA"],
        }
    return {
        "economy": f"This conflict may affect economic stability in the {country_code} region, with potential energy and commodity price volatility.",
        "trade": f"Potential impact on trade with the affected region. Supply chain disruptions should be monitored.",
        "travel": f"Exercise caution when traveling to the area. Flight disruptions possible.",
        "summary": f"Severity {severity}/100 conflict requiring attention across economy, trade, and travel.",
        "score": score,
        "data_sources": ["World Bank", "UN OCHA"],
    }


@router.get("/brief/{cluster_id}", response_model=ImpactBriefOut)
async def get_impact_brief(
    cluster_id: str,
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
):
    """이슈의 경제/무역/여행 영향 분석 (Pro 이상)"""
    # 캐시 확인
    redis = await get_redis()
    cache_key = _brief_cache_key(cluster_id, user.home_country or "KR")
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return ImpactBriefOut(**data)

    # 클러스터 조회
    result = await db.execute(
        select(IssueCluster).where(IssueCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, detail="Cluster not found")

    # 사용자 언어 감지
    lang = "ko"  # default
    from backend.app.models.user import UserPreference
    pref_q = await db.execute(
        select(UserPreference.lang).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    # AI 분석 생성
    brief = await _generate_impact_brief(cluster, user.home_country or "KR", lang, db)

    response_data = {
        "cluster_id": str(cluster.id),
        "title": cluster.title or "",
        "title_ko": cluster.title_ko,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
        **brief,
    }

    # 6시간 캐시
    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=6 * 3600)

    return ImpactBriefOut(**response_data)


# ── Phase 3: Sector Impact Analysis ────────────────────────────────────────

class SectorExposure(BaseModel):
    sector: str
    exposure_pct: float = Field(description="GDP exposure percentage")
    trade_dependency: float = Field(description="Trade dependency 0-1")
    risk_level: str = Field(description="low|medium|high|critical")
    description: str


class SectorAnalysisOut(BaseModel):
    home_country: str
    affected_country: str
    sectors: list[SectorExposure]
    overall_risk: str
    generated_at: str
    cached: bool = False


# 정적 섹터 데이터 (공개 데이터 기반: World Bank, UN Comtrade 참조)
SECTOR_DATA = {
    "KR": {
        "energy": {"gdp_pct": 3.2, "key_partners": ["SA", "AE", "IQ", "KW", "RU"]},
        "semiconductor": {"gdp_pct": 4.8, "key_partners": ["US", "CN", "JP", "TW", "VN"]},
        "automotive": {"gdp_pct": 3.5, "key_partners": ["US", "EU", "CN", "IN"]},
        "agriculture": {"gdp_pct": 1.8, "key_partners": ["US", "AU", "BR", "UA", "RU"]},
        "shipping": {"gdp_pct": 2.1, "key_partners": ["CN", "JP", "US", "SG", "VN"]},
        "tourism": {"gdp_pct": 2.8, "key_partners": ["CN", "JP", "US", "TW", "TH"]},
    },
    "US": {
        "energy": {"gdp_pct": 5.8, "key_partners": ["CA", "SA", "MX", "RU", "IQ"]},
        "technology": {"gdp_pct": 8.2, "key_partners": ["CN", "TW", "KR", "JP", "IE"]},
        "automotive": {"gdp_pct": 3.0, "key_partners": ["MX", "CA", "JP", "DE", "KR"]},
        "agriculture": {"gdp_pct": 4.5, "key_partners": ["CN", "CA", "MX", "JP", "EU"]},
        "defense": {"gdp_pct": 3.4, "key_partners": ["GB", "AU", "JP", "KR", "IL"]},
        "tourism": {"gdp_pct": 2.6, "key_partners": ["MX", "CA", "GB", "JP", "CN"]},
    },
    "JP": {
        "energy": {"gdp_pct": 3.8, "key_partners": ["SA", "AE", "AU", "QA", "RU"]},
        "automotive": {"gdp_pct": 5.2, "key_partners": ["US", "CN", "EU", "TH", "ID"]},
        "electronics": {"gdp_pct": 4.1, "key_partners": ["CN", "US", "KR", "TW", "TH"]},
        "agriculture": {"gdp_pct": 1.1, "key_partners": ["US", "AU", "CA", "BR", "TH"]},
        "shipping": {"gdp_pct": 1.8, "key_partners": ["CN", "US", "KR", "AU", "TW"]},
        "tourism": {"gdp_pct": 1.5, "key_partners": ["CN", "KR", "TW", "US", "TH"]},
    },
}

# Default sectors for countries without specific data
DEFAULT_SECTORS = {
    "energy": {"gdp_pct": 3.0, "key_partners": []},
    "manufacturing": {"gdp_pct": 15.0, "key_partners": []},
    "agriculture": {"gdp_pct": 5.0, "key_partners": []},
    "services": {"gdp_pct": 50.0, "key_partners": []},
    "tourism": {"gdp_pct": 3.0, "key_partners": []},
}

SECTOR_LABELS = {
    "ko": {
        "energy": "에너지", "semiconductor": "반도체", "automotive": "자동차",
        "agriculture": "농업", "shipping": "해운/물류", "tourism": "관광",
        "technology": "기술", "defense": "방위", "electronics": "전자",
        "manufacturing": "제조업", "services": "서비스업",
    },
    "en": {
        "energy": "Energy", "semiconductor": "Semiconductors", "automotive": "Automotive",
        "agriculture": "Agriculture", "shipping": "Shipping & Logistics", "tourism": "Tourism",
        "technology": "Technology", "defense": "Defense", "electronics": "Electronics",
        "manufacturing": "Manufacturing", "services": "Services",
    },
}


def _calc_sector_exposure(
    home_country: str,
    affected_country: str,
    severity: int,
    lang: str = "ko",
) -> list[dict]:
    """정적 데이터 기반 섹터 노출도 계산"""
    sectors_data = SECTOR_DATA.get(home_country, DEFAULT_SECTORS)
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    result = []

    for sector, info in sectors_data.items():
        partners = info.get("key_partners", [])
        gdp_pct = info["gdp_pct"]

        # 영향받는 국가가 핵심 파트너인지 확인
        is_partner = affected_country in partners
        partner_rank = partners.index(affected_country) + 1 if is_partner else 0

        # 교역 의존도 계산 (파트너 순위 기반)
        if partner_rank == 1:
            trade_dep = 0.85
        elif partner_rank == 2:
            trade_dep = 0.6
        elif partner_rank <= 3:
            trade_dep = 0.4
        elif is_partner:
            trade_dep = 0.2
        else:
            trade_dep = 0.05

        # 리스크 레벨
        risk_score = trade_dep * (severity / 100)
        if risk_score >= 0.6:
            risk_level = "critical"
        elif risk_score >= 0.4:
            risk_level = "high"
        elif risk_score >= 0.2:
            risk_level = "medium"
        else:
            risk_level = "low"

        sector_label = labels.get(sector, sector)
        if lang == "ko":
            desc = f"GDP 대비 {gdp_pct}% 비중. "
            if is_partner:
                desc += f"해당 지역은 {sector_label} 분야 {partner_rank}위 교역 파트너."
            else:
                desc += f"해당 지역과 직접 교역 비중은 낮음."
        else:
            desc = f"{gdp_pct}% of GDP. "
            if is_partner:
                desc += f"Affected region is #{partner_rank} trade partner for {sector_label}."
            else:
                desc += f"Low direct trade exposure with the affected region."

        result.append({
            "sector": sector_label,
            "exposure_pct": gdp_pct,
            "trade_dependency": round(trade_dep, 2),
            "risk_level": risk_level,
            "description": desc,
        })

    # 리스크 높은 순 정렬
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    result.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
    return result


@router.get("/sector/{cluster_id}", response_model=SectorAnalysisOut)
async def get_sector_analysis(
    cluster_id: str,
    user: User = Depends(plan_required("pro_plus")),
    db: AsyncSession = Depends(get_db),
):
    """섹터별 영향도 분석 (Pro+ 이상)"""
    redis = await get_redis()
    home = user.home_country or "KR"
    cache_key = f"impact:sector:{cluster_id}:{home}"

    if redis:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return SectorAnalysisOut(**data)

    result = await db.execute(
        select(IssueCluster).where(IssueCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, detail="Cluster not found")

    affected = cluster.country_code or "Unknown"

    # 사용자 언어
    lang = "ko"
    from backend.app.models.user import UserPreference
    pref_q = await db.execute(
        select(UserPreference.lang).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    sectors = _calc_sector_exposure(home, affected, cluster.severity or 0, lang)
    critical_count = sum(1 for s in sectors if s["risk_level"] == "critical")
    high_count = sum(1 for s in sectors if s["risk_level"] == "high")

    if critical_count >= 2:
        overall = "critical"
    elif critical_count >= 1 or high_count >= 2:
        overall = "high"
    elif high_count >= 1:
        overall = "medium"
    else:
        overall = "low"

    response_data = {
        "home_country": home,
        "affected_country": affected,
        "sectors": sectors,
        "overall_risk": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }

    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=12 * 3600)

    return SectorAnalysisOut(**response_data)


# ── Phase 4: Weekly Report ─────────────────────────────────────────────────

class WeeklyReportIssue(BaseModel):
    cluster_id: str
    title: str
    kscore: float
    impact_score: int
    country_codes: list[str]
    topic: str


class WeeklyReportOut(BaseModel):
    week_start: str
    week_end: str
    home_country: str
    top_issues: list[WeeklyReportIssue]
    tension_summary: dict
    total_events: int
    highlight: str
    generated_at: str


@router.get("/weekly-report", response_model=WeeklyReportOut)
async def get_weekly_report(
    user: User = Depends(plan_required("pro_plus")),
    db: AsyncSession = Depends(get_db),
):
    """주간 영향 리포트 (Pro+ 이상)"""
    home = user.home_country or "KR"
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)

    # 사용자 언어
    lang = "ko"
    from backend.app.models.user import UserPreference
    pref_q = await db.execute(
        select(UserPreference.lang).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    # 주간 상위 이슈 (KScore 기준)
    clusters_q = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,
            IssueCluster.last_event_at >= week_start,
            IssueCluster.severity > 0,
            IssueCluster.kscore > 0,
        )
        .order_by(IssueCluster.kscore.desc())
        .limit(10)
    )
    clusters = clusters_q.scalars().all()

    top_issues = []
    for c in clusters:
        impact = min(100, int((c.severity or 0) * 0.7 + (c.kscore or 0) * 3))
        top_issues.append(WeeklyReportIssue(
            cluster_id=str(c.id),
            title=c.title_ko if lang == "ko" and c.title_ko else c.title or "",
            kscore=round(c.kscore or 0, 1),
            impact_score=impact,
            country_codes=[c.country_code] if c.country_code else [],
            topic=c.topic or "unknown",
        ))

    # 주간 이벤트 수
    event_count_q = await db.execute(
        select(func.count(NormalizedEvent.id))
        .where(NormalizedEvent.event_time >= week_start)
    )
    total_events = event_count_q.scalar() or 0

    # 긴장도 변화 요약
    from backend.app.models.tension import TensionIndex
    tension_q = await db.execute(
        select(TensionIndex)
        .where(
            TensionIndex.country_code == home,
            TensionIndex.calculated_at >= week_start,
        )
        .order_by(TensionIndex.calculated_at.desc())
        .limit(1)
    )
    latest_tension = tension_q.scalar_one_or_none()

    tension_week_ago_q = await db.execute(
        select(TensionIndex)
        .where(
            TensionIndex.country_code == home,
            TensionIndex.calculated_at >= week_start - timedelta(hours=6),
            TensionIndex.calculated_at <= week_start + timedelta(hours=6),
        )
        .order_by(TensionIndex.calculated_at.asc())
        .limit(1)
    )
    week_ago_tension = tension_week_ago_q.scalar_one_or_none()

    current_score = latest_tension.raw_score if latest_tension else 0
    prev_score = week_ago_tension.raw_score if week_ago_tension else 0
    delta = round(current_score - prev_score, 1)

    tension_summary = {
        "current": current_score,
        "previous": prev_score,
        "delta": delta,
        "trend": "up" if delta > 0 else ("down" if delta < 0 else "stable"),
    }

    # 하이라이트
    if lang == "ko":
        if len(top_issues) > 0:
            highlight = f"이번 주 {len(top_issues)}건의 주요 이슈가 감지되었습니다. {home} 긴장도는 {current_score}/100 ({'+' if delta > 0 else ''}{delta})입니다."
        else:
            highlight = f"이번 주 특별한 위기 이슈가 없었습니다. {home} 긴장도 {current_score}/100."
    else:
        if len(top_issues) > 0:
            highlight = f"{len(top_issues)} major issues detected this week. {home} tension: {current_score}/100 ({'+' if delta > 0 else ''}{delta})."
        else:
            highlight = f"No significant crisis this week. {home} tension: {current_score}/100."

    return WeeklyReportOut(
        week_start=week_start.isoformat(),
        week_end=now.isoformat(),
        home_country=home,
        top_issues=top_issues,
        tension_summary=tension_summary,
        total_events=total_events,
        highlight=highlight,
        generated_at=now.isoformat(),
    )


# ── Phase 5: Behavior Tracking ────────────────────────────────────────────

class TrackEventIn(BaseModel):
    event_name: str = Field(max_length=100)
    props: dict = Field(default_factory=dict)


class RecommendationsOut(BaseModel):
    recommended_countries: list[str]
    recommended_topics: list[str]
    based_on: str


@router.post("/track")
async def track_behavior(
    body: TrackEventIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 행동 이벤트 기록 (모든 플랜)"""
    from backend.app.models.app_event import AppEvent
    event = AppEvent(
        user_id=user.id,
        name=body.event_name,
        props=body.props,
        platform="web",
    )
    db.add(event)
    await db.flush()
    return {"ok": True}


@router.get("/recommendations", response_model=RecommendationsOut)
async def get_recommendations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """행동 기반 추천 (모든 플랜)"""
    from backend.app.models.app_event import AppEvent

    # 최근 30일 행동 데이터 분석
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # 자주 본 클러스터에서 국가/토픽 추출
    events_q = await db.execute(
        select(AppEvent.props)
        .where(
            AppEvent.user_id == user.id,
            AppEvent.created_at >= since,
            AppEvent.name.in_(["cluster_view", "issue_view", "cluster_card_click"]),
        )
        .order_by(AppEvent.created_at.desc())
        .limit(100)
    )
    events = events_q.scalars().all()

    country_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}

    for props in events:
        if not isinstance(props, dict):
            continue
        cc = props.get("country_code")
        topic = props.get("topic")
        if cc:
            country_counts[cc] = country_counts.get(cc, 0) + 1
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # 상위 5개 추출
    top_countries = sorted(country_counts, key=country_counts.get, reverse=True)[:5]
    top_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:5]

    total = len(events)
    based_on = f"Based on {total} interactions in the last 30 days" if total > 0 else "No behavior data yet"

    return RecommendationsOut(
        recommended_countries=top_countries,
        recommended_topics=top_topics,
        based_on=based_on,
    )
