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

from worker.processor.calibration import (
    IMPACT_FACTORS,
    TOPIC_IMPACT_WEIGHTS,
    DEFAULT_IMPACT_FACTOR,
)

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/impact", tags=["impact"])

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")


def calc_impact_factor(
    event_country: str,
    topic: str,
    home_country: str = "KR",
) -> float:
    """서버사이드 impact factor 계산 (calibration.py 데이터 기반)"""
    if not home_country:
        return 1.0
    country_factors = IMPACT_FACTORS.get(home_country)
    if not country_factors:
        return DEFAULT_IMPACT_FACTOR
    f = country_factors.get(event_country)
    if not f:
        return DEFAULT_IMPACT_FACTOR
    w = TOPIC_IMPACT_WEIGHTS.get(topic, TOPIC_IMPACT_WEIGHTS.get("unknown", {}))
    return w.get("geo", 0.33) * f.get("geo", 0.5) + \
           w.get("sec", 0.34) * f.get("sec", 0.5) + \
           w.get("eco", 0.33) * f.get("eco", 0.5)


def calc_personalized_impact_score(
    severity: int,
    kscore: float,
    event_country: str,
    topic: str,
    home_country: str,
) -> int:
    """개인화된 Impact Score (0-100)

    공식: severity × impact_factor × topic_weight_boost + kscore_contribution
    - impact_factor: 사용자 홈 국가와 이벤트 국가 간 관계 (0-1)
    - topic_weight_boost: 토픽별 가중 (conflict/terror = 높음, diplomacy = 낮음)
    - kscore_contribution: KScore × 2 (트렌드 반영, 기존 3에서 조정)
    """
    factor = calc_impact_factor(event_country, topic, home_country)

    # 토픽별 심각도 부스터 (conflict/terror = 1.2, diplomacy/health = 0.8)
    topic_severity_boost = {
        "conflict": 1.2, "terror": 1.3, "coup": 1.2,
        "sanctions": 1.0, "cyber": 0.9, "protest": 0.8,
        "diplomacy": 0.7, "maritime": 0.9, "disaster": 1.0,
        "health": 0.8, "unknown": 0.9,
    }
    boost = topic_severity_boost.get(topic, 0.9)

    # 최종 계산: severity 기반(70%) + kscore 기반(30%)
    severity_component = severity * factor * boost * 0.7
    kscore_component = min(30, kscore * 3)  # KScore max 10 × 3 = 30

    return min(100, max(0, int(severity_component + kscore_component)))


# ── Impact Summary (홀리스틱 종합 영향도) ──────────────────────────────────

class ImpactSummaryTopIssue(BaseModel):
    cluster_id: str
    title: str
    impact_score: int
    country_codes: list[str]
    topic: str
    reason: Optional[str] = None
    kscore_delta: Optional[float] = None


class CommoditySnapshotOut(BaseModel):
    symbol: str
    name: str
    price_usd: float
    change_pct: float


class MarketIndexSnapshotOut(BaseModel):
    symbol: str
    name: str
    value: float
    change_pct: float
    currency: str


class ExchangeRateSnapshotOut(BaseModel):
    target_currency: str
    rate: float
    change_pct: Optional[float] = None


class MarketSnapshotOut(BaseModel):
    commodities: list[CommoditySnapshotOut] = []
    indices: list[MarketIndexSnapshotOut] = []
    exchange_rates: list[ExchangeRateSnapshotOut] = []


class TradePartnerOut(BaseModel):
    country_code: str
    trade_volume_usd: float
    dependency_pct: float


class TradeExposureOut(BaseModel):
    top_partners: list[TradePartnerOut] = []
    total_trade_volume: float = 0


class TravelAlertOut(BaseModel):
    country_code: str
    level: int
    title: Optional[str] = None
    source: str


class ImpactSummaryOut(BaseModel):
    score: int = Field(ge=0, le=100, description="종합 영향도 0-100")
    level: str = Field(description="low|guarded|elevated|high")
    summary: str
    economy: Optional[str] = None
    trade: Optional[str] = None
    travel: Optional[str] = None
    top_issues: list[ImpactSummaryTopIssue] = []
    affected_sectors_count: int = 0
    critical_issues_count: int = 0
    total_active_issues: int = 0
    data_sources: list[str] = []
    generated_at: str
    cached: bool = False
    market_snapshot: Optional[MarketSnapshotOut] = None
    trade_exposure: Optional[TradeExposureOut] = None
    travel_advisories: list[TravelAlertOut] = []


@router.get("/summary", response_model=ImpactSummaryOut)
async def get_impact_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """홀리스틱 종합 영향도 (모든 플랜).

    사용자 홈 국가에 영향을 미치는 모든 활성 클러스터를 종합하여
    안정적인 영향도 점수와 요약을 반환합니다.
    - Free: score + summary + top_issues_count
    - Pro/Pro+: economy/trade/travel 상세 분석 포함
    """
    home = user.home_country or "KR"
    user_plan = user.plan or "free"

    # 캐시 확인 (plan별로 — Pro가 상세 정보 포함하므로)
    redis = get_redis()
    cache_key = f"impact:summary:{home}:{user_plan}"
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            # Phase 2 필드가 없는 구버전 캐시는 무시
            if "market_snapshot" in data:
                data["cached"] = True
                return ImpactSummaryOut(**data)
            else:
                await redis.delete(cache_key)

    # 사용자 언어
    lang = "ko"
    from backend.app.models.user import UserPreference
    pref_q = await db.execute(
        select(UserPreference.language).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    # 최근 7일 활성 클러스터 가져오기
    since = datetime.now(timezone.utc) - timedelta(days=7)
    clusters_q = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,
            IssueCluster.severity > 0,
            IssueCluster.kscore > 0,
            IssueCluster.last_event_at >= since,
        )
        .order_by(IssueCluster.kscore.desc())
        .limit(100)
    )
    clusters = clusters_q.scalars().all()

    # 각 클러스터에 대해 personalized impact score 계산
    scored = []
    for c in clusters:
        cc = c.country_code or ""
        topic = c.topic or "unknown"
        impact = calc_personalized_impact_score(
            c.severity or 0, c.kscore or 0, cc, topic, home,
        )
        scored.append((c, impact))

    # impact score 기준 정렬 (안정적 — 같은 데이터면 같은 결과)
    scored.sort(key=lambda x: (-x[1], str(x[0].id)))

    total_active = len(scored)
    critical_count = sum(1 for _, s in scored if s >= 70)

    # 종합 점수: 상위 10개 가중 평균 (1위: 30%, 2위: 20%, 3~5위: 10%, 6~10위: 6%)
    weights = [0.30, 0.20, 0.10, 0.10, 0.10, 0.06, 0.06, 0.04, 0.02, 0.02]
    top_10 = scored[:10]
    if top_10:
        total_weight = sum(weights[:len(top_10)])
        weighted_sum = sum(
            s * (weights[i] if i < len(weights) else 0.02)
            for i, (_, s) in enumerate(top_10)
        )
        overall_score = min(100, max(0, int(weighted_sum / total_weight)))
    else:
        overall_score = 0

    # 레벨
    if overall_score >= 75:
        level = "high"
    elif overall_score >= 50:
        level = "elevated"
    elif overall_score >= 25:
        level = "guarded"
    else:
        level = "low"

    # 영향받는 섹터 수 계산
    sectors_data = SECTOR_DATA.get(home, DEFAULT_SECTORS)
    affected_sectors = set()
    for c, _ in top_10:
        cc = c.country_code or ""
        for sector, info in sectors_data.items():
            if cc in info.get("key_partners", []):
                affected_sectors.add(sector)

    # Top 5 이슈 + reason + kscore_delta
    top_issues = []
    for c, impact in scored[:5]:
        # reason 생성 (교역 데이터 + 시장 가격 기반)
        reason = await _generate_issue_reason(c, home, lang, sectors_data, db)

        # kscore_delta: 24시간 변화량 (클러스터 kscore 기반)
        kscore_delta = None
        try:
            from backend.app.models.issue_cluster import ClusterEvent
            day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            # 24시간 전 kscore와 비교 (간단히: 현재 kscore - 24h전 kscore)
            old_cluster_q = await db.execute(
                select(IssueCluster.kscore)
                .where(IssueCluster.id == c.id)
                .limit(1)
            )
            current_kscore = c.kscore or 0
            # kscore 변화를 근사: 최근 24h 이벤트 수 기반
            recent_events_q = await db.execute(
                select(func.count(ClusterEvent.id))
                .where(
                    ClusterEvent.cluster_id == c.id,
                    ClusterEvent.created_at >= day_ago,
                )
            )
            recent_count = recent_events_q.scalar() or 0
            if recent_count > 0:
                kscore_delta = round(min(5.0, recent_count * 0.5), 1)
            else:
                kscore_delta = round(-min(1.0, current_kscore * 0.1), 1) if current_kscore > 1 else 0
        except Exception:
            pass

        top_issues.append(ImpactSummaryTopIssue(
            cluster_id=str(c.id),
            title=c.title_ko if lang == "ko" and c.title_ko else c.title or "",
            impact_score=impact,
            country_codes=[c.country_code] if c.country_code else [],
            topic=c.topic or "unknown",
            reason=reason,
            kscore_delta=kscore_delta,
        ))

    # 홈 국가 긴장도 조회
    from backend.app.models.tension_index import TensionIndex
    tension_q = await db.execute(
        select(TensionIndex.raw_score)
        .where(TensionIndex.country_code == home)
        .order_by(TensionIndex.time.desc())
        .limit(1)
    )
    home_tension = tension_q.scalar_one_or_none() or 0

    # 요약 생성 (모든 플랜)
    level_ko = {"high": "높음", "elevated": "경계", "guarded": "주의", "low": "안정"}
    level_en = {"high": "High", "elevated": "Elevated", "guarded": "Guarded", "low": "Low"}

    if lang == "ko":
        summary = f"현재 {home} 영향도 {overall_score}/100 ({level_ko.get(level, level)}). "
        if critical_count > 0:
            summary += f"고영향 이슈 {critical_count}건 감지. "
        if total_active > 0:
            summary += f"최근 7일간 {total_active}건의 활성 이슈가 모니터링 중."
        else:
            summary += "현재 주요 위기 이슈 없음."
    else:
        summary = f"{home} impact: {overall_score}/100 ({level_en.get(level, level)}). "
        if critical_count > 0:
            summary += f"{critical_count} high-impact issue(s) detected. "
        if total_active > 0:
            summary += f"{total_active} active issues monitored in the last 7 days."
        else:
            summary += "No major crisis issues at this time."

    # Pro 이상: 상세 분석 (economy/trade/travel)
    economy = None
    trade = None
    travel = None

    is_pro = user_plan in ("pro", "pro_plus") or getattr(user, "admin_plan_override", False)

    if is_pro and top_10:
        from backend.app.models.economic_data import CommodityPrice, MarketIndex, TradeBilateral, TravelAdvisory
        from backend.app.models.tension_index import TensionIndex as TI2

        # 상위 이슈들의 국가/토픽 분석
        top_countries = {}
        top_topics = {}
        for c, impact in top_10:
            cc = c.country_code or ""
            topic = c.topic or "unknown"
            if cc:
                top_countries[cc] = max(top_countries.get(cc, 0), impact)
            top_topics[topic] = max(top_topics.get(topic, 0), impact)

        high_impact_countries = [cc for cc, s in sorted(top_countries.items(), key=lambda x: -x[1]) if s >= 50][:3]
        labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
        sector_details = [labels.get(s, s) for s in affected_sectors]

        # ── 실제 데이터 조회 (분석에 활용) ──
        # 유가
        oil_q = await db.execute(
            select(CommodityPrice.price_usd, CommodityPrice.change_pct)
            .where(CommodityPrice.symbol == "WTI")
            .order_by(CommodityPrice.price_date.desc()).limit(1)
        )
        oil_row = oil_q.first()
        oil_str = f"${oil_row[0]:,.0f}({oil_row[1]:+.1f}%)" if oil_row else None

        # 금
        gold_q = await db.execute(
            select(CommodityPrice.price_usd, CommodityPrice.change_pct)
            .where(CommodityPrice.symbol == "GOLD")
            .order_by(CommodityPrice.price_date.desc()).limit(1)
        )
        gold_row = gold_q.first()

        # 홈 국가 주가지수
        home_idx_map = {"KR": "KOSPI", "US": "SPX", "JP": "NKY", "CN": "SSE", "DE": "DAX", "GB": "FTSE"}
        home_idx_sym = home_idx_map.get(home)
        idx_str = None
        if home_idx_sym:
            idx_q = await db.execute(
                select(MarketIndex.name, MarketIndex.change_pct)
                .where(MarketIndex.symbol == home_idx_sym)
                .order_by(MarketIndex.index_date.desc()).limit(1)
            )
            idx_row = idx_q.first()
            if idx_row:
                idx_str = f"{idx_row[0]} {idx_row[1]:+.1f}%"

        # 주요 교역 파트너별 교역액 (상위 3개국)
        trade_vols = {}
        for hc in list(top_countries.keys())[:5]:
            tv_q = await db.execute(
                select(TradeBilateral.total_trade_usd)
                .where(TradeBilateral.reporter_code == home, TradeBilateral.partner_code == hc, TradeBilateral.period_type == "A")
                .order_by(TradeBilateral.period.desc()).limit(1)
            )
            tv = tv_q.scalar_one_or_none()
            if tv and tv > 0:
                trade_vols[hc] = tv

        def _fmt_usd(v):
            if v >= 1e9: return f"${v/1e9:.1f}B"
            if v >= 1e6: return f"${v/1e6:.0f}M"
            return f"${v:,.0f}"

        # 여행 경보 Lv.4 국가 수
        lv4_q = await db.execute(
            select(func.count(TravelAdvisory.id))
            .where(TravelAdvisory.level == 4)
        )
        lv4_count = lv4_q.scalar() or 0

        # 에너지 관련 국가 이슈 여부
        energy_partners = set(sectors_data.get("energy", {}).get("key_partners", []))
        energy_risk = bool(energy_partners & set(top_countries.keys()))

        if lang == "ko":
            # ── Economy: 시장 데이터 + 섹터 영향 ──
            econ_parts = []
            if energy_risk and oil_str:
                econ_parts.append(f"중동 분쟁 심화로 유가 {oil_str} 급등, {home} 에너지 수입비용 상승 압력")
            elif oil_str:
                econ_parts.append(f"유가 {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"금 ${gold_row[0]:,.0f}({gold_row[1]:+.1f}%) 안전자산 수요 증가")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details and not energy_risk:
                econ_parts.append(f"{', '.join(sector_details[:3])} 분야 공급망 리스크 주시")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"{home} 경제 영향 모니터링 중."

            # ── Trade: 교역 데이터 기반 ──
            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{home}-{top_tv[0]} 교역 {_fmt_usd(top_tv[1])}이 최대 노출 지점")
                if len(sorted_tv) > 1:
                    others = ", ".join(f"{c}({_fmt_usd(v)})" for c, v in sorted_tv[1:3])
                    trade_parts.append(f"{others} 교역도 분쟁 영향권")
            if energy_risk:
                trade_parts.append("에너지 수입 의존국 불안정으로 원유 공급 리스크")
            if not trade_parts:
                trade_parts.append(f"{home} 관련 직접 교역 리스크는 제한적이나 간접 파급 주시")
            trade = ". ".join(trade_parts) + "."

            # ── Travel: 여행 경보 데이터 기반 ──
            travel_parts = []
            if lv4_count > 0:
                lv4_names_q = await db.execute(
                    select(TravelAdvisory.country_code)
                    .where(TravelAdvisory.level == 4, TravelAdvisory.country_code.in_(list(top_countries.keys())))
                )
                lv4_in_issues = [r[0] for r in lv4_names_q.all()]
                if lv4_in_issues:
                    travel_parts.append(f"이슈 관련 {len(lv4_in_issues)}개국 여행금지(Lv.4): {', '.join(lv4_in_issues[:4])}")
                travel_parts.append(f"전 세계 {lv4_count}개국이 여행금지 상태")
            if critical_count > 0:
                travel_parts.append(f"고영향 이슈 {critical_count}건 관련 지역 항공편 변동 주의")
            if not travel_parts:
                travel_parts.append("현재 관심 지역 주요 여행 제한 없음")
            travel = ". ".join(travel_parts) + "."
        else:
            # ── English ──
            econ_parts = []
            if energy_risk and oil_str:
                econ_parts.append(f"Oil {oil_str} surging amid Middle East tensions, raising {home} energy import costs")
            elif oil_str:
                econ_parts.append(f"Oil {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"Gold ${gold_row[0]:,.0f} ({gold_row[1]:+.1f}%) on safe-haven demand")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details and not energy_risk:
                econ_parts.append(f"{', '.join(sector_details[:3])} supply chain risk to monitor")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"Monitoring economic impact on {home}."

            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{home}-{top_tv[0]} trade at {_fmt_usd(top_tv[1])} is primary exposure")
                if len(sorted_tv) > 1:
                    others = ", ".join(f"{c} ({_fmt_usd(v)})" for c, v in sorted_tv[1:3])
                    trade_parts.append(f"{others} trade also in conflict zone")
            if energy_risk:
                trade_parts.append("Energy import dependencies at risk from regional instability")
            if not trade_parts:
                trade_parts.append(f"Direct trade exposure for {home} is limited; watch indirect spillover")
            trade = ". ".join(trade_parts) + "."

            travel_parts = []
            if lv4_count > 0:
                travel_parts.append(f"{lv4_count} countries at Do Not Travel (Lv.4) globally")
            if critical_count > 0:
                travel_parts.append(f"{critical_count} high-impact issues may affect flights and transit")
            if not travel_parts:
                travel_parts.append("No major travel restrictions for areas of interest")
            travel = ". ".join(travel_parts) + "."

    # ── 시장 동향 (market_snapshot) — 모든 플랜 ──
    market_snapshot = None
    try:
        market_snapshot = await _get_market_snapshot(home, db)
    except Exception as e:
        logger.warning("market_snapshot_error", error=str(e))

    # ── 교역 노출도 (trade_exposure) — Pro 이상 ──
    trade_exposure = None
    if is_pro:
        try:
            trade_exposure = await _get_trade_exposure(home, db)
        except Exception as e:
            logger.warning("trade_exposure_error", error=str(e))

    # ── 여행 경보 (travel_advisories) — 모든 플랜 ──
    travel_advisories = []
    try:
        travel_advisories = await _get_travel_advisories(home, scored[:10], is_pro, db)
    except Exception as e:
        logger.warning("travel_advisories_error", error=str(e))

    data_sources = ["World Bank", "UN Comtrade", "IMF IMTS"]
    if market_snapshot and (market_snapshot.get("commodities") or market_snapshot.get("indices")):
        data_sources.append("Yahoo Finance")
    if travel_advisories:
        data_sources.append("US State Dept")

    response_data = {
        "score": overall_score,
        "level": level,
        "summary": summary,
        "economy": economy,
        "trade": trade,
        "travel": travel,
        "top_issues": [ti.model_dump() for ti in top_issues],
        "affected_sectors_count": len(affected_sectors),
        "critical_issues_count": critical_count,
        "total_active_issues": total_active,
        "data_sources": data_sources,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
        "market_snapshot": market_snapshot,
        "trade_exposure": trade_exposure,
        "travel_advisories": travel_advisories,
    }

    # 6시간 캐시
    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=6 * 3600)

    return ImpactSummaryOut(**response_data)


# ── Phase 2: Impact Brief (per-cluster, legacy) ─────────────────────────

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

    # Impact factor 계산 (GPT 컨텍스트 강화용)
    impact_factor = calc_impact_factor(country_code, cluster_topic, home_country)
    impact_score = calc_personalized_impact_score(
        cluster.severity or 0, cluster.kscore or 0,
        country_code, cluster_topic, home_country,
    )

    # 홈 국가-영향 국가 간 교역 관계 파악
    sector_data = SECTOR_DATA.get(home_country, {})
    related_sectors = []
    for sector, info in sector_data.items():
        if country_code in info.get("key_partners", []):
            rank = info["key_partners"].index(country_code) + 1
            labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
            related_sectors.append(f"{labels.get(sector, sector)} (#{rank} partner, {info['gdp_pct']}% GDP)")
    trade_context = "\n".join(f"- {s}" for s in related_sectors) if related_sectors else "No major direct trade relationship."

    # Tier 2: DB에서 실 교역 데이터 보강
    try:
        from backend.app.models.economic_data import TradeBilateral, EconomicIndicator
        trade_q = await db.execute(
            select(TradeBilateral.total_trade_usd, TradeBilateral.period)
            .where(
                TradeBilateral.reporter_code == home_country,
                TradeBilateral.partner_code == country_code,
                TradeBilateral.period_type == "A",
            )
            .order_by(TradeBilateral.period.desc())
            .limit(1)
        )
        trade_row = trade_q.first()
        if trade_row and trade_row[0]:
            trade_context += f"\n- Bilateral trade volume: ${trade_row[0]:,.0f}M USD ({trade_row[1]})"

        # GDP 데이터
        for cc in [home_country, country_code]:
            gdp_q = await db.execute(
                select(EconomicIndicator.value, EconomicIndicator.year)
                .where(
                    EconomicIndicator.country_code == cc,
                    EconomicIndicator.indicator_code == "NY.GDP.MKTP.CD",
                )
                .order_by(EconomicIndicator.year.desc())
                .limit(1)
            )
            gdp_row = gdp_q.first()
            if gdp_row and gdp_row[0]:
                trade_context += f"\n- {cc} GDP: ${gdp_row[0] / 1e9:,.1f}B USD ({gdp_row[1]})"
    except Exception:
        pass  # Tier 2 테이블 미생성 시 무시

    # 긴장도 데이터 조회
    from backend.app.models.tension_index import TensionIndex
    tension_q = await db.execute(
        select(TensionIndex.raw_score)
        .where(TensionIndex.country_code == country_code)
        .order_by(TensionIndex.time.desc())
        .limit(1)
    )
    tension_score = tension_q.scalar_one_or_none() or 0

    if OPENAI_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)

            system_prompt = """You are an expert geopolitical risk analyst providing impact assessments for a conflict monitoring platform.

Analyze how a global conflict/crisis affects a specific country across three dimensions:
1. Economy: GDP growth, inflation, supply chain disruption, energy/commodity prices, currency stability
2. Trade: bilateral trade volumes, import/export disruption, sanctions impact, shipping routes, supply chain alternatives
3. Travel: safety advisories, flight availability, visa restrictions, insurance coverage

CRITICAL RULES:
- NEVER give investment advice, mention stocks/securities, or recommend financial actions
- Use hedging language: "potential impact", "may affect", "likely to influence"
- Base analysis on the provided data context (trade relationships, severity, tension scores)
- Cite specific data sources (World Bank, UN Comtrade, IMF, OECD)
- Each section: 2-3 sentences with specific data points
- Impact score MUST correlate with severity, trade dependency, and proximity factors
- If trade dependency is high, score should reflect this proportionally
- Respond in the requested language"""

            user_prompt = f"""Analyze impact on {home_country}:

Crisis: {cluster_title}
Topic: {cluster_topic}
Affected region: {country_code}
Region tension index: {tension_score}/100
Severity: {cluster.severity}/100
KScore (trend intensity): {cluster.kscore or 0:.1f}/10
Impact factor ({home_country}→{country_code}): {impact_factor:.2f}
Calculated impact score: {impact_score}/100

Trade relationship ({home_country} sectors affected by {country_code}):
{trade_context}

Recent events:
{events_text}

Respond in {"Korean" if lang == "ko" else "English"} as JSON:
{{"economy": "...", "trade": "...", "travel": "...", "summary": "one-line summary", "score": {impact_score}, "data_sources": ["World Bank", ...]}}

Note: The score should be close to {impact_score} (pre-calculated based on trade dependency and severity). You may adjust ±10 based on qualitative factors."""

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

    # Fallback: 규칙 기반 분석 (실제 데이터 포인트 반영)
    severity = cluster.severity or 0
    score = impact_score

    # 실제 교역 데이터 파싱
    trade_vol_str = ""
    gdp_str = ""
    for line in trade_context.split("\n"):
        if "Bilateral trade" in line:
            trade_vol_str = line.split(": ")[-1] if ": " in line else ""
        if f"{home_country} GDP" in line:
            gdp_str = line.split(": ")[-1] if ": " in line else ""

    sectors_affected = [s.split(" (")[0].strip("- ") for s in related_sectors]
    sectors_str = ", ".join(sectors_affected[:3]) if sectors_affected else ""

    tension_label = (
        "극심" if tension_score >= 80 else
        "심각" if tension_score >= 60 else
        "경계" if tension_score >= 40 else
        "주의" if tension_score >= 20 else "안정"
    )
    tension_label_en = (
        "extreme" if tension_score >= 80 else
        "severe" if tension_score >= 60 else
        "elevated" if tension_score >= 40 else
        "guarded" if tension_score >= 20 else "stable"
    )

    if lang == "ko":
        economy = f"{country_code} 지역 긴장도 {tension_score:.0f}/100({tension_label}). "
        if trade_vol_str:
            economy += f"양자 교역 규모 {trade_vol_str}. "
        economy += f"에너지·원자재 가격 변동 및 환율 영향 가능성."

        trade = ""
        if sectors_str:
            trade = f"{home_country}의 {sectors_str} 분야가 영향권. "
        if trade_vol_str:
            trade += f"교역 규모 {trade_vol_str}으로 공급망 차질 모니터링 필요."
        else:
            trade += f"해당 지역과 직접 교역 비중은 낮으나 간접 파급 주의."

        travel = f"해당 지역 여행 주의 (심각도 {severity}/100). "
        if tension_score >= 60:
            travel += "항공편 변동·경유 제한 가능성 높음."
        else:
            travel += "현지 안전 공지 확인 권장."

        summary = f"{cluster_title[:50]} — {home_country} 영향도 {score}/100"
        if sectors_str:
            summary += f" ({sectors_str} 영향)"

        return {
            "economy": economy,
            "trade": trade,
            "travel": travel,
            "summary": summary,
            "score": score,
            "data_sources": ["World Bank", "UN Comtrade", "IMF IMTS"],
        }

    # English
    economy = f"{country_code} tension at {tension_score:.0f}/100 ({tension_label_en}). "
    if trade_vol_str:
        economy += f"Bilateral trade volume: {trade_vol_str}. "
    economy += "Potential impact on energy, commodities and FX."

    trade = ""
    if sectors_str:
        trade = f"{home_country}'s {sectors_str} sectors exposed. "
    if trade_vol_str:
        trade += f"Trade volume {trade_vol_str} — monitor supply chain disruptions."
    else:
        trade += "Low direct trade exposure; watch for indirect spillover."

    travel = f"Exercise caution (severity {severity}/100). "
    if tension_score >= 60:
        travel += "High likelihood of flight disruptions and transit restrictions."
    else:
        travel += "Check local advisories before traveling."

    summary = f"{cluster_title[:50]} — Impact on {home_country}: {score}/100"
    if sectors_str:
        summary += f" ({sectors_str} exposed)"

    return {
        "economy": economy,
        "trade": trade,
        "travel": travel,
        "summary": summary,
        "score": score,
        "data_sources": ["World Bank", "UN Comtrade", "IMF IMTS"],
    }


@router.get("/brief/{cluster_id}", response_model=ImpactBriefOut)
async def get_impact_brief(
    cluster_id: str,
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
):
    """이슈의 경제/무역/여행 영향 분석 (Pro 이상)"""
    # 캐시 확인
    redis = get_redis()
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
        select(UserPreference.language).where(UserPreference.user_id == user.id)
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

    # 12시간 캐시 (비용 최적화: TTL 6h→12h)
    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=12 * 3600)

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


# 정적 섹터 데이터 (공개 데이터 기반: World Bank, UN Comtrade, OECD 참조)
# GDP 비중은 해당 국가 2023-2024 기준 근사치
SECTOR_DATA = {
    "KR": {
        "energy": {"gdp_pct": 3.2, "key_partners": ["SA", "AE", "IQ", "KW", "RU"]},
        "semiconductor": {"gdp_pct": 4.8, "key_partners": ["US", "CN", "JP", "TW", "VN"]},
        "automotive": {"gdp_pct": 3.5, "key_partners": ["US", "CN", "IN", "DE"]},
        "agriculture": {"gdp_pct": 1.8, "key_partners": ["US", "AU", "BR", "UA", "RU"]},
        "shipping": {"gdp_pct": 2.1, "key_partners": ["CN", "JP", "US", "SG", "VN"]},
        "tourism": {"gdp_pct": 2.8, "key_partners": ["CN", "JP", "US", "TW", "TH"]},
    },
    "US": {
        "energy": {"gdp_pct": 5.8, "key_partners": ["CA", "SA", "MX", "RU", "IQ"]},
        "technology": {"gdp_pct": 8.2, "key_partners": ["CN", "TW", "KR", "JP", "IE"]},
        "automotive": {"gdp_pct": 3.0, "key_partners": ["MX", "CA", "JP", "DE", "KR"]},
        "agriculture": {"gdp_pct": 4.5, "key_partners": ["CN", "CA", "MX", "JP", "BR"]},
        "defense": {"gdp_pct": 3.4, "key_partners": ["GB", "AU", "JP", "KR", "IL"]},
        "tourism": {"gdp_pct": 2.6, "key_partners": ["MX", "CA", "GB", "JP", "CN"]},
    },
    "JP": {
        "energy": {"gdp_pct": 3.8, "key_partners": ["SA", "AE", "AU", "QA", "RU"]},
        "automotive": {"gdp_pct": 5.2, "key_partners": ["US", "CN", "TH", "ID", "DE"]},
        "electronics": {"gdp_pct": 4.1, "key_partners": ["CN", "US", "KR", "TW", "TH"]},
        "agriculture": {"gdp_pct": 1.1, "key_partners": ["US", "AU", "CA", "BR", "TH"]},
        "shipping": {"gdp_pct": 1.8, "key_partners": ["CN", "US", "KR", "AU", "TW"]},
        "tourism": {"gdp_pct": 1.5, "key_partners": ["CN", "KR", "TW", "US", "TH"]},
    },
    "CN": {
        "energy": {"gdp_pct": 6.5, "key_partners": ["SA", "RU", "IQ", "AE", "IR"]},
        "technology": {"gdp_pct": 7.5, "key_partners": ["US", "KR", "TW", "JP", "DE"]},
        "manufacturing": {"gdp_pct": 27.0, "key_partners": ["US", "JP", "KR", "DE", "VN"]},
        "agriculture": {"gdp_pct": 7.3, "key_partners": ["BR", "US", "AU", "AR", "CA"]},
        "shipping": {"gdp_pct": 3.5, "key_partners": ["US", "JP", "KR", "SG", "DE"]},
        "tourism": {"gdp_pct": 2.2, "key_partners": ["TH", "JP", "KR", "US", "SG"]},
    },
    "DE": {
        "energy": {"gdp_pct": 3.5, "key_partners": ["NO", "US", "NL", "RU", "GB"]},
        "automotive": {"gdp_pct": 5.0, "key_partners": ["US", "CN", "GB", "FR", "IT"]},
        "manufacturing": {"gdp_pct": 19.7, "key_partners": ["US", "CN", "FR", "NL", "PL"]},
        "agriculture": {"gdp_pct": 0.8, "key_partners": ["NL", "FR", "PL", "IT", "ES"]},
        "tourism": {"gdp_pct": 2.5, "key_partners": ["NL", "CH", "AT", "US", "GB"]},
    },
    "GB": {
        "energy": {"gdp_pct": 3.2, "key_partners": ["NO", "US", "NL", "QA", "SA"]},
        "finance": {"gdp_pct": 8.3, "key_partners": ["US", "DE", "FR", "NL", "JP"]},
        "technology": {"gdp_pct": 5.5, "key_partners": ["US", "DE", "IE", "NL", "CN"]},
        "agriculture": {"gdp_pct": 0.6, "key_partners": ["IE", "NL", "FR", "DE", "ES"]},
        "tourism": {"gdp_pct": 3.0, "key_partners": ["US", "FR", "DE", "IE", "ES"]},
    },
    "FR": {
        "energy": {"gdp_pct": 2.8, "key_partners": ["NO", "SA", "US", "RU", "NE"]},
        "automotive": {"gdp_pct": 2.5, "key_partners": ["DE", "ES", "IT", "GB", "BE"]},
        "agriculture": {"gdp_pct": 1.7, "key_partners": ["DE", "BE", "IT", "ES", "NL"]},
        "tourism": {"gdp_pct": 4.2, "key_partners": ["GB", "DE", "BE", "NL", "US"]},
        "defense": {"gdp_pct": 1.9, "key_partners": ["US", "GB", "DE", "IN", "SA"]},
    },
    "AU": {
        "energy": {"gdp_pct": 8.5, "key_partners": ["CN", "JP", "KR", "IN", "TW"]},
        "mining": {"gdp_pct": 10.5, "key_partners": ["CN", "JP", "KR", "IN", "US"]},
        "agriculture": {"gdp_pct": 2.3, "key_partners": ["CN", "JP", "US", "KR", "ID"]},
        "tourism": {"gdp_pct": 2.8, "key_partners": ["NZ", "CN", "US", "GB", "JP"]},
        "technology": {"gdp_pct": 3.5, "key_partners": ["US", "NZ", "SG", "GB", "JP"]},
    },
    "IN": {
        "energy": {"gdp_pct": 4.5, "key_partners": ["SA", "IQ", "AE", "RU", "KW"]},
        "technology": {"gdp_pct": 8.0, "key_partners": ["US", "GB", "SG", "DE", "JP"]},
        "agriculture": {"gdp_pct": 17.0, "key_partners": ["US", "AE", "CN", "BD", "NL"]},
        "manufacturing": {"gdp_pct": 14.0, "key_partners": ["US", "AE", "CN", "HK", "SG"]},
        "tourism": {"gdp_pct": 2.5, "key_partners": ["BD", "US", "GB", "SG", "AE"]},
    },
    "BR": {
        "energy": {"gdp_pct": 4.0, "key_partners": ["US", "CN", "AR", "NL", "CL"]},
        "agriculture": {"gdp_pct": 7.5, "key_partners": ["CN", "US", "NL", "JP", "DE"]},
        "mining": {"gdp_pct": 4.5, "key_partners": ["CN", "US", "JP", "AR", "NL"]},
        "manufacturing": {"gdp_pct": 11.0, "key_partners": ["US", "AR", "CN", "MX", "DE"]},
        "tourism": {"gdp_pct": 2.0, "key_partners": ["AR", "US", "CL", "PY", "UY"]},
    },
    "SA": {
        "energy": {"gdp_pct": 40.0, "key_partners": ["CN", "IN", "JP", "KR", "US"]},
        "construction": {"gdp_pct": 5.5, "key_partners": ["CN", "US", "GB", "DE", "FR"]},
        "tourism": {"gdp_pct": 3.5, "key_partners": ["EG", "PK", "IN", "ID", "BD"]},
        "manufacturing": {"gdp_pct": 12.0, "key_partners": ["CN", "US", "DE", "JP", "IT"]},
    },
    "AE": {
        "energy": {"gdp_pct": 30.0, "key_partners": ["JP", "IN", "CN", "KR", "TH"]},
        "finance": {"gdp_pct": 9.0, "key_partners": ["US", "GB", "IN", "SA", "CN"]},
        "tourism": {"gdp_pct": 5.5, "key_partners": ["IN", "GB", "SA", "RU", "CN"]},
        "shipping": {"gdp_pct": 4.0, "key_partners": ["CN", "IN", "US", "SA", "JP"]},
    },
    "IL": {
        "technology": {"gdp_pct": 12.0, "key_partners": ["US", "CN", "GB", "DE", "IN"]},
        "defense": {"gdp_pct": 5.2, "key_partners": ["US", "DE", "IN", "IT", "GB"]},
        "agriculture": {"gdp_pct": 1.1, "key_partners": ["NL", "GB", "FR", "DE", "US"]},
        "tourism": {"gdp_pct": 2.8, "key_partners": ["US", "FR", "DE", "GB", "RU"]},
    },
    "TR": {
        "manufacturing": {"gdp_pct": 20.0, "key_partners": ["DE", "US", "GB", "IT", "IQ"]},
        "agriculture": {"gdp_pct": 6.5, "key_partners": ["IQ", "DE", "RU", "US", "GB"]},
        "energy": {"gdp_pct": 3.0, "key_partners": ["RU", "IR", "IQ", "AZ", "SA"]},
        "tourism": {"gdp_pct": 4.5, "key_partners": ["DE", "RU", "GB", "BG", "GE"]},
        "automotive": {"gdp_pct": 3.5, "key_partners": ["DE", "GB", "FR", "IT", "US"]},
    },
    "TW": {
        "semiconductor": {"gdp_pct": 15.0, "key_partners": ["US", "CN", "JP", "KR", "SG"]},
        "electronics": {"gdp_pct": 8.0, "key_partners": ["CN", "US", "JP", "KR", "HK"]},
        "manufacturing": {"gdp_pct": 30.0, "key_partners": ["CN", "US", "JP", "HK", "KR"]},
        "agriculture": {"gdp_pct": 1.5, "key_partners": ["US", "BR", "AU", "NZ", "JP"]},
        "tourism": {"gdp_pct": 1.8, "key_partners": ["JP", "KR", "CN", "US", "HK"]},
    },
    "TH": {
        "tourism": {"gdp_pct": 11.5, "key_partners": ["CN", "MY", "KR", "IN", "JP"]},
        "automotive": {"gdp_pct": 5.5, "key_partners": ["US", "AU", "JP", "CN", "MY"]},
        "agriculture": {"gdp_pct": 8.5, "key_partners": ["CN", "US", "JP", "VN", "MY"]},
        "electronics": {"gdp_pct": 6.0, "key_partners": ["US", "CN", "JP", "HK", "SG"]},
        "energy": {"gdp_pct": 3.5, "key_partners": ["SA", "AE", "QA", "MY", "KW"]},
    },
    "VN": {
        "manufacturing": {"gdp_pct": 25.0, "key_partners": ["US", "CN", "KR", "JP", "NL"]},
        "electronics": {"gdp_pct": 8.0, "key_partners": ["US", "CN", "KR", "JP", "HK"]},
        "agriculture": {"gdp_pct": 12.0, "key_partners": ["US", "CN", "JP", "KR", "PH"]},
        "tourism": {"gdp_pct": 3.0, "key_partners": ["KR", "CN", "JP", "TW", "US"]},
        "energy": {"gdp_pct": 3.0, "key_partners": ["CN", "JP", "KR", "MY", "SG"]},
    },
    "SG": {
        "finance": {"gdp_pct": 13.5, "key_partners": ["US", "CN", "GB", "HK", "JP"]},
        "shipping": {"gdp_pct": 7.0, "key_partners": ["CN", "MY", "US", "ID", "JP"]},
        "technology": {"gdp_pct": 9.0, "key_partners": ["US", "CN", "MY", "JP", "KR"]},
        "tourism": {"gdp_pct": 4.0, "key_partners": ["ID", "CN", "IN", "MY", "AU"]},
        "manufacturing": {"gdp_pct": 20.0, "key_partners": ["CN", "MY", "US", "HK", "JP"]},
    },
    "CA": {
        "energy": {"gdp_pct": 10.0, "key_partners": ["US", "CN", "GB", "JP", "KR"]},
        "mining": {"gdp_pct": 5.0, "key_partners": ["US", "CN", "GB", "JP", "DE"]},
        "agriculture": {"gdp_pct": 1.8, "key_partners": ["US", "CN", "JP", "MX", "GB"]},
        "automotive": {"gdp_pct": 2.5, "key_partners": ["US", "MX", "JP", "DE", "KR"]},
        "technology": {"gdp_pct": 5.0, "key_partners": ["US", "GB", "DE", "FR", "CN"]},
        "tourism": {"gdp_pct": 2.0, "key_partners": ["US", "GB", "FR", "MX", "DE"]},
    },
    "MX": {
        "manufacturing": {"gdp_pct": 18.0, "key_partners": ["US", "CN", "CA", "DE", "JP"]},
        "energy": {"gdp_pct": 5.5, "key_partners": ["US", "ES", "NL", "CN", "IN"]},
        "automotive": {"gdp_pct": 4.0, "key_partners": ["US", "CA", "DE", "JP", "BR"]},
        "agriculture": {"gdp_pct": 3.5, "key_partners": ["US", "JP", "CA", "CN", "GT"]},
        "tourism": {"gdp_pct": 3.5, "key_partners": ["US", "CA", "GB", "CO", "AR"]},
    },
    "RU": {
        "energy": {"gdp_pct": 25.0, "key_partners": ["CN", "IN", "TR", "DE", "NL"]},
        "mining": {"gdp_pct": 8.0, "key_partners": ["CN", "NL", "DE", "TR", "KR"]},
        "agriculture": {"gdp_pct": 4.0, "key_partners": ["TR", "CN", "EG", "KZ", "BY"]},
        "defense": {"gdp_pct": 3.9, "key_partners": ["IN", "CN", "EG", "DZ", "VN"]},
        "manufacturing": {"gdp_pct": 13.0, "key_partners": ["CN", "BY", "KZ", "TR", "DE"]},
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
        "finance": "금융", "mining": "광업", "construction": "건설",
    },
    "en": {
        "energy": "Energy", "semiconductor": "Semiconductors", "automotive": "Automotive",
        "agriculture": "Agriculture", "shipping": "Shipping & Logistics", "tourism": "Tourism",
        "technology": "Technology", "defense": "Defense", "electronics": "Electronics",
        "manufacturing": "Manufacturing", "services": "Services",
        "finance": "Finance", "mining": "Mining", "construction": "Construction",
    },
}


# ── Phase 2 헬퍼 함수들 ─────────────────────────────────────────────────

# 홈 국가 통화 매핑 (주요 환율 표시용)
_HOME_CURRENCIES = {
    "KR": ["KRW", "JPY", "CNY", "EUR"],
    "US": ["EUR", "JPY", "GBP", "CNY"],
    "JP": ["JPY", "KRW", "CNY", "EUR"],
    "CN": ["CNY", "JPY", "KRW", "EUR"],
    "DE": ["EUR", "GBP", "JPY", "CNY"],
    "GB": ["GBP", "EUR", "JPY", "CNY"],
}


async def _generate_issue_reason(
    cluster,
    home_country: str,
    lang: str,
    sectors_data: dict,
    db: AsyncSession,
) -> str:
    """이슈가 나에게 영향이 큰 이유를 구체적으로 1줄 생성.

    교역 데이터, 섹터 GDP 비중, 시장 가격을 활용해 "왜 나에게 위험한지" 명확히 설명.
    """
    from backend.app.models.economic_data import TradeBilateral, CommodityPrice

    cc = cluster.country_code or ""
    topic = cluster.topic or "unknown"
    severity = cluster.severity or 0
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])

    # 1) 영향받는 섹터 + GDP 비중
    affected_sectors = []  # [(label, gdp_pct)]
    for sector, info in sectors_data.items():
        if cc in info.get("key_partners", []):
            affected_sectors.append((labels.get(sector, sector), info.get("gdp_pct", 0)))
    # GDP 비중 높은 순 정렬
    affected_sectors.sort(key=lambda x: -x[1])

    # 2) 실제 양자간 교역액 조회
    trade_vol = None
    try:
        trade_q = await db.execute(
            select(TradeBilateral.total_trade_usd)
            .where(
                TradeBilateral.reporter_code == home_country,
                TradeBilateral.partner_code == cc,
                TradeBilateral.period_type == "A",
            )
            .order_by(TradeBilateral.period.desc())
            .limit(1)
        )
        trade_vol = trade_q.scalar_one_or_none()
    except Exception:
        pass

    # 3) 에너지 관련 이슈면 유가 데이터 활용
    oil_price = None
    if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY"):
        try:
            oil_q = await db.execute(
                select(CommodityPrice.price_usd, CommodityPrice.change_pct)
                .where(CommodityPrice.symbol == "WTI")
                .order_by(CommodityPrice.price_date.desc())
                .limit(1)
            )
            row = oil_q.first()
            if row:
                oil_price = (row[0], row[1])
        except Exception:
            pass

    # 4) 교역액 포맷
    trade_str = ""
    if trade_vol and trade_vol > 0:
        if trade_vol >= 1e9:
            trade_str = f"${trade_vol / 1e9:.1f}B"
        elif trade_vol >= 1e6:
            trade_str = f"${trade_vol / 1e6:.0f}M"

    # 5) 구체적 reason 생성
    if lang == "ko":
        if affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            reason = f"{home_country}-{cc} 교역 {trade_str}, {top_sector}(GDP {gdp}%) 공급망에 직접 영향"
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {home_country} {top_sector} 비용 직접 상승 압력"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {home_country} 에너지(GDP {gdp}%) 비용 상승"
            elif len(affected_sectors) >= 2:
                reason = f"{home_country} {affected_sectors[0][0]}(GDP {affected_sectors[0][1]}%)·{affected_sectors[1][0]} 분야 공급망 리스크"
            else:
                reason = f"{home_country} {top_sector}(GDP {gdp}%) 분야에 직접 영향"
        elif trade_str:
            reason = f"{home_country}-{cc} 교역 {trade_str}, 교역 관계 통한 간접 파급"
        elif severity >= 70:
            if topic in ("conflict", "terror"):
                reason = "고강도 군사 충돌로 글로벌 공급망·금융시장 불안정"
            else:
                reason = "심각도 높은 이슈로 국제 경제 전반에 파급 우려"
        elif topic == "sanctions":
            reason = "경제 제재 확대 시 원자재·부품 수급 차질 가능"
        elif topic == "disaster":
            reason = "자연재해로 인한 물류·제조 공급망 차질 우려"
        else:
            reason = "국제 정세 변동에 따른 시장 불확실성 증가"
    else:
        if affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            reason = f"{home_country}-{cc} trade {trade_str}, direct {top_sector} (GDP {gdp}%) supply chain exposure"
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), rising {top_sector} costs for {home_country}"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), {home_country} energy (GDP {gdp}%) cost pressure"
            elif len(affected_sectors) >= 2:
                reason = f"{home_country} {affected_sectors[0][0]} (GDP {affected_sectors[0][1]}%) & {affected_sectors[1][0]} supply chain risk"
            else:
                reason = f"Direct impact on {home_country}'s {top_sector} sector (GDP {gdp}%)"
        elif trade_str:
            reason = f"{home_country}-{cc} trade {trade_str}, indirect spillover via trade links"
        elif severity >= 70:
            reason = "High-intensity crisis causing global supply chain and market instability"
        elif topic == "sanctions":
            reason = "Sanctions expansion may disrupt raw material and component supply"
        elif topic == "disaster":
            reason = "Natural disaster causing logistics and manufacturing disruptions"
        else:
            reason = "Increased market uncertainty from geopolitical developments"

    return reason


async def _get_market_snapshot(
    home_country: str,
    db: AsyncSession,
) -> dict | None:
    """시장 동향 스냅샷: 원자재 + 환율 + 주가지수"""
    from backend.app.models.economic_data import CommodityPrice, MarketIndex, ExchangeRate

    commodities = []
    indices = []
    exchange_rates = []

    # 원자재 최신 가격
    for symbol in ["WTI", "BRENT", "GOLD"]:
        q = await db.execute(
            select(CommodityPrice)
            .where(CommodityPrice.symbol == symbol)
            .order_by(CommodityPrice.price_date.desc())
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row:
            commodities.append({
                "symbol": row.symbol,
                "name": row.name,
                "price_usd": row.price_usd,
                "change_pct": row.change_pct,
            })

    # 주가지수 최신
    for symbol in ["KOSPI", "SPX", "NKY", "DAX", "FTSE", "SSE"]:
        q = await db.execute(
            select(MarketIndex)
            .where(MarketIndex.symbol == symbol)
            .order_by(MarketIndex.index_date.desc())
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row:
            indices.append({
                "symbol": row.symbol,
                "name": row.name,
                "value": row.value,
                "change_pct": row.change_pct,
                "currency": row.currency,
            })

    # 환율 (홈 국가 기준 주요 통화)
    target_currencies = _HOME_CURRENCIES.get(home_country, ["EUR", "JPY", "GBP", "CNY"])
    for tc in target_currencies:
        q = await db.execute(
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == "USD",
                ExchangeRate.target_currency == tc,
            )
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row:
            # 전일 대비 변동률 계산
            prev_q = await db.execute(
                select(ExchangeRate.rate)
                .where(
                    ExchangeRate.base_currency == "USD",
                    ExchangeRate.target_currency == tc,
                    ExchangeRate.rate_date < row.rate_date,
                )
                .order_by(ExchangeRate.rate_date.desc())
                .limit(1)
            )
            prev_rate = prev_q.scalar_one_or_none()
            change_pct = None
            if prev_rate and prev_rate > 0:
                change_pct = round(((row.rate - prev_rate) / prev_rate) * 100, 2)

            exchange_rates.append({
                "target_currency": row.target_currency,
                "rate": row.rate,
                "change_pct": change_pct,
            })

    if not commodities and not indices and not exchange_rates:
        return None

    return {
        "commodities": commodities,
        "indices": indices,
        "exchange_rates": exchange_rates,
    }


async def _get_trade_exposure(
    home_country: str,
    db: AsyncSession,
) -> dict | None:
    """교역 노출도: 상위 5개 교역국 + 의존도%"""
    from backend.app.models.economic_data import TradeBilateral

    # 상위 교역 파트너 (최신 연도)
    q = await db.execute(
        select(
            TradeBilateral.partner_code,
            TradeBilateral.total_trade_usd,
        )
        .where(
            TradeBilateral.reporter_code == home_country,
            TradeBilateral.period_type == "A",
        )
        .order_by(TradeBilateral.period.desc(), TradeBilateral.total_trade_usd.desc())
    )
    rows = q.all()
    if not rows:
        return None

    # 최신 연도의 데이터만 (같은 period)
    # rows는 이미 period desc + trade desc로 정렬
    # 같은 파트너 중복 제거 (최신 연도 우선)
    seen = set()
    partners = []
    for partner_code, trade_usd in rows:
        if partner_code in seen or trade_usd is None:
            continue
        seen.add(partner_code)
        partners.append((partner_code, trade_usd))
        if len(partners) >= 5:
            break

    total_trade = sum(t for _, t in partners)
    if total_trade <= 0:
        return None

    top_partners = []
    for pc, tv in partners:
        dep = round((tv / total_trade) * 100, 1)
        top_partners.append({
            "country_code": pc,
            "trade_volume_usd": tv,
            "dependency_pct": dep,
        })

    return {
        "top_partners": top_partners,
        "total_trade_volume": total_trade,
    }


async def _get_travel_advisories(
    home_country: str,
    scored_clusters: list,
    is_pro: bool,
    db: AsyncSession,
) -> list[dict]:
    """여행 경보: 관심국 + 이슈 관련 국가"""
    from backend.app.models.economic_data import TravelAdvisory
    from backend.app.models.user import UserArea

    # 이슈 관련 국가
    issue_countries = set()
    for c, _ in scored_clusters:
        if c.country_code:
            issue_countries.add(c.country_code)

    # 사용자 관심 국가
    interest_q = await db.execute(
        select(UserArea.country_code)
        .where(UserArea.country_code.isnot(None))
        .limit(20)
    )
    interest_countries = {r[0] for r in interest_q.all() if r[0]}

    target_countries = issue_countries | interest_countries
    if home_country:
        target_countries.add(home_country)

    if not target_countries:
        return []

    # DB에서 여행 경보 조회
    advisories_q = await db.execute(
        select(TravelAdvisory)
        .where(TravelAdvisory.country_code.in_(list(target_countries)))
        .order_by(TravelAdvisory.level.desc())
    )
    advisories = advisories_q.scalars().all()

    results = []
    seen = set()
    for adv in advisories:
        if adv.country_code in seen:
            continue
        seen.add(adv.country_code)

        alert = {
            "country_code": adv.country_code,
            "level": adv.level,
            "source": adv.source,
        }
        # Pro: 상세 제목 포함
        if is_pro:
            alert["title"] = adv.title
        results.append(alert)

    # Level 2+ 만 반환 (Level 1은 노이즈)
    results = [r for r in results if r["level"] >= 2]

    return results[:10]


async def _get_real_trade_dependency(
    home_country: str,
    affected_country: str,
    db: AsyncSession,
) -> float | None:
    """DB에서 실제 양자간 교역 비중 조회 (Tier 2)

    Returns: 0-1 사이 교역 의존도 (데이터 없으면 None)
    """
    from backend.app.models.economic_data import TradeBilateral

    # 1) reporter→partner 교역액 (최신 연도)
    pair_q = await db.execute(
        select(TradeBilateral.total_trade_usd)
        .where(
            TradeBilateral.reporter_code == home_country,
            TradeBilateral.partner_code == affected_country,
            TradeBilateral.period_type == "A",
        )
        .order_by(TradeBilateral.period.desc())
        .limit(1)
    )
    pair_trade = pair_q.scalar_one_or_none()
    if pair_trade is None:
        return None

    # 2) reporter 전체 교역액 (같은 연도) — 가용한 파트너 합계로 근사
    total_q = await db.execute(
        select(func.sum(TradeBilateral.total_trade_usd))
        .where(
            TradeBilateral.reporter_code == home_country,
            TradeBilateral.period_type == "A",
        )
    )
    total_trade = total_q.scalar_one_or_none()
    if not total_trade or total_trade <= 0:
        return None

    # 교역 의존도 = 해당 파트너와의 교역 / 전체 교역 합계
    # 이 값은 0-1 범위의 상대적 비중 (실제 전체 교역의 일부만 DB에 있으므로 근사치)
    dep = min(1.0, pair_trade / total_trade)
    return round(dep, 3)


async def _calc_sector_exposure(
    home_country: str,
    affected_country: str,
    severity: int,
    lang: str = "ko",
    db: AsyncSession | None = None,
) -> list[dict]:
    """섹터 노출도 계산 (실 데이터 있으면 보정, 없으면 하드코딩 fallback)"""
    sectors_data = SECTOR_DATA.get(home_country, DEFAULT_SECTORS)
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])

    # Tier 2: DB에서 실제 교역 의존도 조회 (옵셔널 보정)
    real_trade_dep = None
    if db:
        try:
            real_trade_dep = await _get_real_trade_dependency(home_country, affected_country, db)
        except Exception:
            pass  # 테이블 미생성 시 무시

    result = []

    for sector, info in sectors_data.items():
        partners = info.get("key_partners", [])
        gdp_pct = info["gdp_pct"]

        # 영향받는 국가가 핵심 파트너인지 확인
        is_partner = affected_country in partners
        partner_rank = partners.index(affected_country) + 1 if is_partner else 0

        # 교역 의존도 계산: 실 데이터 > 순위 기반 fallback
        if real_trade_dep is not None and is_partner:
            # 실 데이터 보정: 실제 교역 비중 × 파트너 순위 가중
            rank_weight = max(0.3, 1.0 - (partner_rank - 1) * 0.15)
            trade_dep = min(0.95, real_trade_dep * rank_weight * 3)  # ×3: 교역 비중을 의존도 스케일로 확대
        elif partner_rank == 1:
            trade_dep = 0.85
        elif partner_rank == 2:
            trade_dep = 0.6
        elif partner_rank <= 3:
            trade_dep = 0.4
        elif is_partner:
            trade_dep = 0.2
        else:
            trade_dep = 0.05 if real_trade_dep is None else min(0.15, real_trade_dep * 2)

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

        # 설명 생성 (실 데이터 유무에 따라 다른 문구)
        data_source = " (IMF)" if real_trade_dep is not None else ""
        if lang == "ko":
            desc = f"GDP 대비 {gdp_pct}% 비중. "
            if is_partner:
                desc += f"해당 지역은 {sector_label} 분야 {partner_rank}위 교역 파트너."
                if real_trade_dep is not None:
                    desc += f" 실제 교역 비중 {real_trade_dep * 100:.1f}%{data_source}."
            else:
                desc += f"해당 지역과 직접 교역 비중은 낮음."
        else:
            desc = f"{gdp_pct}% of GDP. "
            if is_partner:
                desc += f"Affected region is #{partner_rank} trade partner for {sector_label}."
                if real_trade_dep is not None:
                    desc += f" Actual trade share: {real_trade_dep * 100:.1f}%{data_source}."
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
    redis = get_redis()
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
        select(UserPreference.language).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    sectors = await _calc_sector_exposure(home, affected, cluster.severity or 0, lang, db)
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
        select(UserPreference.language).where(UserPreference.user_id == user.id)
    )
    pref_lang = pref_q.scalar_one_or_none()
    if pref_lang:
        lang = pref_lang

    # 주간 상위 이슈 (personalizedKScore 기준)
    clusters_q = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,
            IssueCluster.last_event_at >= week_start,
            IssueCluster.severity > 0,
            IssueCluster.kscore > 0,
        )
        .order_by(IssueCluster.kscore.desc())
        .limit(50)  # 더 많이 가져와서 personalized 정렬
    )
    clusters = clusters_q.scalars().all()

    # personalizedKScore로 재정렬
    scored_clusters = []
    for c in clusters:
        cc = c.country_code or ""
        topic = c.topic or "unknown"
        factor = calc_impact_factor(cc, topic, home)
        personalized_ks = (c.kscore or 0) * factor
        impact = calc_personalized_impact_score(
            c.severity or 0, c.kscore or 0, cc, topic, home,
        )
        scored_clusters.append((c, personalized_ks, impact))

    scored_clusters.sort(key=lambda x: x[1], reverse=True)

    top_issues = []
    for c, _, impact in scored_clusters[:10]:
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
    from backend.app.models.tension_index import TensionIndex
    tension_q = await db.execute(
        select(TensionIndex)
        .where(
            TensionIndex.country_code == home,
            TensionIndex.time >= week_start,
        )
        .order_by(TensionIndex.time.desc())
        .limit(1)
    )
    latest_tension = tension_q.scalar_one_or_none()

    tension_week_ago_q = await db.execute(
        select(TensionIndex)
        .where(
            TensionIndex.country_code == home,
            TensionIndex.time >= week_start - timedelta(hours=6),
            TensionIndex.time <= week_start + timedelta(hours=6),
        )
        .order_by(TensionIndex.time.asc())
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

    # 하이라이트 — 최고 영향 이슈 포함
    top_title = top_issues[0].title if top_issues else ""
    top_impact = top_issues[0].impact_score if top_issues else 0
    critical_count = sum(1 for i in top_issues if i.impact_score >= 70)

    if lang == "ko":
        if len(top_issues) > 0:
            highlight = f"이번 주 {len(top_issues)}건의 주요 이슈가 감지되었습니다. "
            if critical_count > 0:
                highlight += f"영향도 높은 이슈 {critical_count}건. "
            highlight += f"{home} 긴장도 {current_score}/100 ({'+' if delta > 0 else ''}{delta})."
        else:
            highlight = f"이번 주 특별한 위기 이슈가 없었습니다. {home} 긴장도 {current_score}/100."
    else:
        if len(top_issues) > 0:
            highlight = f"{len(top_issues)} major issues detected this week. "
            if critical_count > 0:
                highlight += f"{critical_count} high-impact issue(s). "
            highlight += f"{home} tension: {current_score}/100 ({'+' if delta > 0 else ''}{delta})."
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


# ── Phase 6: Trade Flow (Sankey) ─────────────────────────────────────────

class TradeFlowNode(BaseModel):
    id: str
    label: str


class TradeFlowLink(BaseModel):
    source: str
    target: str
    value: float


class TradeFlowOut(BaseModel):
    nodes: list[TradeFlowNode]
    links: list[TradeFlowLink]
    home_country: str
    generated_at: str
    cached: bool = False


@router.get("/trade-flow", response_model=TradeFlowOut)
async def get_trade_flow(
    user: User = Depends(plan_required("pro_plus")),
    db: AsyncSession = Depends(get_db),
):
    """국가간 교역 흐름 Sankey 데이터 (Pro+ 이상)

    DB에 실제 교역 데이터가 있으면 사용, 없으면 SECTOR_DATA 기반 추정.
    """
    home = user.home_country or "KR"
    redis = get_redis()
    cache_key = f"impact:trade-flow:{home}"

    if redis:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return TradeFlowOut(**data)

    nodes_map: dict[str, str] = {}  # code -> label
    links: list[dict] = []

    # 1) DB에서 실제 교역 데이터 조회 (최신 연도)
    real_data_found = False
    try:
        from backend.app.models.economic_data import TradeBilateral
        trade_q = await db.execute(
            select(
                TradeBilateral.partner_code,
                TradeBilateral.export_value_usd,
                TradeBilateral.import_value_usd,
            )
            .where(
                TradeBilateral.reporter_code == home,
                TradeBilateral.period_type == "A",
            )
            .order_by(TradeBilateral.period.desc())
            .limit(20)
        )
        trade_rows = trade_q.fetchall()
        if trade_rows:
            real_data_found = True
    except Exception:
        pass

    if real_data_found and trade_rows:
        # 수출(home→partner)과 수입(partner→home)을 3-column Sankey로 표현
        # 왼쪽: home_export / 가운데: partners / 오른쪽: home_import
        export_node = f"{home}_EXP"
        import_node = f"{home}_IMP"
        nodes_map[export_node] = export_node
        nodes_map[import_node] = import_node

        for row in trade_rows:
            partner = row[0]
            export_val = row[1] or 0
            import_val = row[2] or 0
            if export_val <= 0 and import_val <= 0:
                continue
            export_m = round(export_val / 1e6, 1)
            import_m = round(import_val / 1e6, 1)
            nodes_map[partner] = partner
            if export_m > 0:
                links.append({
                    "source": export_node,
                    "target": partner,
                    "value": export_m,
                })
            if import_m > 0:
                links.append({
                    "source": partner,
                    "target": import_node,
                    "value": import_m,
                })
    else:
        # Fallback: SECTOR_DATA 기반 추정 (백만달러 환산)
        sectors = SECTOR_DATA.get(home, DEFAULT_SECTORS)
        partner_totals: dict[str, float] = {}

        for sector, info in sectors.items():
            gdp_pct = info["gdp_pct"]
            partners = info.get("key_partners", [])
            for i, partner in enumerate(partners[:5]):
                weights = [0.40, 0.25, 0.15, 0.12, 0.08]
                weight = weights[i] if i < len(weights) else 0.05
                val = gdp_pct * weight
                partner_totals[partner] = partner_totals.get(partner, 0) + val

        sorted_partners = sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        nodes_map[home] = home
        for partner, val in sorted_partners:
            nodes_map[partner] = partner
            links.append({
                "source": home,
                "target": partner,
                "value": round(val, 2),
            })

    nodes = [{"id": code, "label": code} for code in nodes_map]

    response_data = {
        "nodes": nodes,
        "links": links,
        "home_country": home,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }

    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=24 * 3600)

    return TradeFlowOut(**response_data)


# ── Phase 7: Weekly Report PDF ──────────────────────────────────────────


class WeeklyPdfOut(BaseModel):
    url: str | None
    week: str
    available: bool


@router.get("/weekly-pdf", response_model=WeeklyPdfOut)
async def get_weekly_pdf(
    user: User = Depends(plan_required("pro_plus")),
):
    """최신 주간 리포트 PDF URL (Pro+ 이상)."""
    import os
    now = datetime.now(timezone.utc)
    week_label = now.strftime("%Y-W%V")
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url:
        return WeeklyPdfOut(url=None, week=week_label, available=False)

    pdf_url = f"{supabase_url}/storage/v1/object/public/weekly-reports/reports/{week_label}.pdf"
    return WeeklyPdfOut(url=pdf_url, week=week_label, available=True)
