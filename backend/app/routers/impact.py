"""
Impact Dashboard endpoints — Phase 2-5

Phase 2: Impact Brief (Pro) — AI-powered impact analysis per cluster
Phase 3: Sector Impact Analysis (Pro+) — sector-level exposure analysis
Phase 4: Weekly Report (Pro+) — weekly impact summary
Phase 5: Behavior Personalization — event tracking + recommendations
"""

import asyncio
import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, plan_required, get_db
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
_CACHE_VERSION = "v16"

# 홈 국가 → 주가지수 심볼 매핑
_HOME_INDEX_MAP: dict[str, str] = {
    "KR": "KOSPI", "US": "SPX", "JP": "NKY", "CN": "SSE", "DE": "DAX", "GB": "FTSE",
    "TW": "TWII", "TH": "SET", "SG": "STI", "IN": "SENSEX", "BR": "BOVESPA",
    "CA": "TSX", "FR": "CAC", "SA": "TASI", "IL": "TA35", "TR": "BIST",
    "AU": "ASX", "MX": "MXX",
    "VN": "VNINDEX", "ID": "JCI", "PH": "PSEI", "PL": "WIG20", "EG": "EGX30",
}

# 국가 코드 → 국가명 (reason 표시용)
_COUNTRY_DISPLAY = {
    "ko": {
        "KR": "한국", "US": "미국", "JP": "일본", "CN": "중국", "DE": "독일", "GB": "영국",
        "FR": "프랑스", "RU": "러시아", "UA": "우크라이나", "IR": "이란", "IQ": "이라크",
        "SA": "사우디", "AE": "UAE", "IL": "이스라엘", "SY": "시리아", "PS": "팔레스타인",
        "TW": "대만", "IN": "인도", "BR": "브라질", "AU": "호주", "CA": "캐나다",
        "TR": "튀르키예", "TH": "태국", "VN": "베트남", "SG": "싱가포르", "MX": "멕시코",
        "KP": "북한", "LB": "레바논", "YE": "예멘", "LY": "리비아", "KW": "쿠웨이트",
        "PK": "파키스탄", "AF": "아프가니스탄", "SD": "수단", "MM": "미얀마",
    },
    "en": {},  # 영어는 코드 그대로 사용
}


def _country_name(code: str, lang: str) -> str:
    """reason 표시용 국가명"""
    names = _COUNTRY_DISPLAY.get(lang, {})
    return names.get(code, code)


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
    title_en: Optional[str] = None
    impact_score: int
    country_codes: list[str]
    topic: str
    reason: Optional[str] = None
    kscore_delta: Optional[float] = None
    event_count: int = 0
    severity: int = 0
    kscore: float = 0.0
    independent_sources: int = 0
    is_spike: bool = False
    confidence: float = 0.0
    first_event_at: Optional[str] = None
    last_event_at: Optional[str] = None
    entity_anchor: str | None = None
    body_snippet: str | None = None
    what_line: str | None = None
    so_what_line: str | None = None
    when_line: str | None = None
    relevant_commodities: list[str] | None = None
    source_tier: str | None = None  # A/B/C/D
    impact_reason: str | None = None  # 1-line reasoning


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
    last_updated_at: Optional[str] = None


class TradePartnerOut(BaseModel):
    country_code: str
    trade_volume_usd: float
    dependency_pct: float
    export_usd: Optional[float] = None
    import_usd: Optional[float] = None
    trade_balance: Optional[str] = None  # "surplus" | "deficit"


class TradeExposureOut(BaseModel):
    top_partners: list[TradePartnerOut] = []
    total_trade_volume: float = 0


class TravelAlertOut(BaseModel):
    country_code: str
    level: int
    title: Optional[str] = None
    source: str


class RiskRadarAxis(BaseModel):
    axis: str
    value: float
    prev_value: float
    label_ko: str
    label_en: str

class RiskRadarOut(BaseModel):
    axes: list[RiskRadarAxis]
    overall_trend: str   # "improving"|"deteriorating"|"stable"

class ImpactFlowNode(BaseModel):
    id: str
    label: str
    sub_label: str | None = None  # 2줄째: 실시간 가격 데이터
    color: str
    category: str
    cluster_id: str | None = None
    country_codes: list[str] = []

class ImpactFlowLink(BaseModel):
    source: str
    target: str
    value: float

class ImpactFlowOut(BaseModel):
    nodes: list[ImpactFlowNode]
    links: list[ImpactFlowLink]


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
    risk_radar: RiskRadarOut | None = None
    impact_flow: ImpactFlowOut | None = None


async def _build_impact_summary(
    home: str, user_plan: str, lang: str, db: AsyncSession,
) -> "ImpactSummaryOut":
    """캐시 워밍에서도 호출 가능한 impact summary 핵심 로직."""
    is_global = not home

    # 캐시 확인 (plan + lang별)
    redis = get_redis()
    cache_key = f"impact:summary:{_CACHE_VERSION}:{home or 'global'}:{user_plan}:{lang}"
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

    # Top 5 이슈: impact_score 기준 (Sankey와 동일한 정렬)
    top5_for_issues = scored[:5]

    from backend.app.models.economic_data import TradeBilateral, CommodityPrice
    from backend.app.models.issue_cluster import ClusterEvent

    top5_countries = list({c.country_code for c, _ in top5_for_issues if c.country_code})
    top5_cluster_ids = [c.id for c, _ in top5_for_issues]

    # 배치 1: TradeBilateral (Top5 국가 교역액)
    trade_map: dict[str, float] = {}
    if top5_countries and home:
        trade_q = await db.execute(
            select(TradeBilateral.partner_code, TradeBilateral.total_trade_usd)
            .where(
                TradeBilateral.reporter_code == home,
                TradeBilateral.partner_code.in_(top5_countries),
                TradeBilateral.period_type == "A",
            )
            .order_by(TradeBilateral.period.desc())
        )
        for row in trade_q.fetchall():
            if row[0] not in trade_map:
                trade_map[row[0]] = row[1]

        # Fallback: 직접 보고 없으면 역방향 (mirror trade)
        missing = [cc for cc in top5_countries if cc not in trade_map]
        if missing:
            mirror_q = await db.execute(
                select(TradeBilateral.reporter_code, TradeBilateral.total_trade_usd)
                .where(
                    TradeBilateral.partner_code == home,
                    TradeBilateral.reporter_code.in_(missing),
                    TradeBilateral.period_type == "A",
                )
                .order_by(TradeBilateral.period.desc())
            )
            for row in mirror_q.fetchall():
                if row[0] not in trade_map:
                    trade_map[row[0]] = row[1]

    # 배치 2: WTI 유가 (공유)
    oil_q = await db.execute(
        select(CommodityPrice.price_usd, CommodityPrice.change_pct)
        .where(CommodityPrice.symbol == "WTI")
        .order_by(CommodityPrice.price_date.desc())
        .limit(1)
    )
    oil_row = oil_q.first()

    # 배치 3: kscore_delta — 최근 24h 이벤트 수 배치
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    delta_q = await db.execute(
        select(ClusterEvent.cluster_id, func.count(ClusterEvent.event_id))
        .join(NormalizedEvent, NormalizedEvent.id == ClusterEvent.event_id)
        .where(
            ClusterEvent.cluster_id.in_(top5_cluster_ids),
            NormalizedEvent.created_at >= day_ago,
        )
        .group_by(ClusterEvent.cluster_id)
    )
    recent_counts = {row[0]: row[1] for row in delta_q.fetchall()}

    # 배치 4: body_ko snippet — 최근 이벤트에서 body_ko 가져오기
    body_snippets: dict[str, str] = {}
    if top5_cluster_ids:
        from backend.app.models.issue_cluster import ClusterEvent as CE4
        body_q = await db.execute(
            select(CE4.cluster_id, NormalizedEvent.body_ko)
            .join(NormalizedEvent, NormalizedEvent.id == CE4.event_id)
            .where(
                CE4.cluster_id.in_(top5_cluster_ids),
                NormalizedEvent.body_ko.isnot(None),
            )
            .order_by(NormalizedEvent.created_at.desc())
            .limit(20)
        )
        for row in body_q.fetchall():
            cid = row[0]
            if cid not in body_snippets and row[1]:
                text = row[1][:150].strip()
                if len(row[1]) > 150:
                    text += "…"
                body_snippets[cid] = text

    # ── 원자재 가격 배치 조회 (reason/summary/impact_flow/risk_radar 공용) ──
    _cp_symbols = ["WTI", "BRENT", "NATGAS", "WHEAT", "CORN", "SOYBEAN", "RICE", "BDRY", "JET_FUEL", "GOLD", "SILVER"]
    _cp_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(_cp_symbols))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )
    commodity_prices: dict[str, tuple[float, float]] = {}  # symbol → (price, change_pct)
    for cp in _cp_q.scalars():
        if cp.symbol not in commodity_prices:
            commodity_prices[cp.symbol] = (cp.price_usd, cp.change_pct or 0)

    top_issues = []
    for c, impact in top5_for_issues:
        reason = _build_reason_sync(c, home, lang, sectors_data, trade_map, oil_row, commodity_prices)
        smart = _build_smart_summary(c, home, lang, sectors_data, trade_map, oil_row, commodity_prices)

        recent_count = recent_counts.get(c.id, 0)
        current_kscore = c.kscore or 0
        if recent_count > 0:
            kscore_delta = round(min(5.0, recent_count * 0.5), 1)
        else:
            kscore_delta = round(-min(1.0, current_kscore * 0.1), 1) if current_kscore > 1 else 0

        # Source Tier: 독립 소스 수 기반 등급 (A: 5+, B: 3-4, C: 2, D: 0-1)
        _src_n = c.independent_sources or 0
        _tier = "A" if _src_n >= 5 else ("B" if _src_n >= 3 else ("C" if _src_n >= 2 else "D"))

        top_issues.append(ImpactSummaryTopIssue(
            cluster_id=str(c.id),
            title=c.title_ko if lang == "ko" and c.title_ko else c.title or "",
            title_en=c.title or "",
            impact_score=impact,
            country_codes=[c.country_code] if c.country_code else [],
            topic=c.topic or "unknown",
            reason=reason,
            kscore_delta=kscore_delta,
            event_count=c.event_count or 0,
            severity=c.severity or 0,
            kscore=round(c.kscore or 0.0, 2),
            independent_sources=_src_n,
            is_spike=c.is_spike or False,
            confidence=round(c.confidence or 0.0, 3),
            first_event_at=c.first_event_at.isoformat() if c.first_event_at else None,
            last_event_at=c.last_event_at.isoformat() if c.last_event_at else None,
            entity_anchor=c.entity_anchor,
            body_snippet=body_snippets.get(c.id),
            what_line=smart["what_line"],
            so_what_line=smart["so_what_line"],
            when_line=smart["when_line"],
            relevant_commodities=smart.get("relevant_commodities"),
            source_tier=_tier,
            impact_reason=reason,
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
        top1 = top_issues[0] if top_issues else None
        parts = []
        if top1:
            parts.append(f"'{top1.title[:20]}' 이슈 영향 가장 큼")
        if critical_count > 0:
            parts.append(f"고영향 {critical_count}건")
        parts.append(f"활성 이슈 {total_active}건" if total_active else "주요 위기 없음")
        summary = " · ".join(parts)
    else:
        top1_en = top_issues[0] if top_issues else None
        parts_en = []
        if top1_en:
            parts_en.append(f"'{top1_en.title[:20]}' has highest impact")
        if critical_count > 0:
            parts_en.append(f"{critical_count} high-impact")
        parts_en.append(f"{total_active} active issues" if total_active else "No major crisis")
        summary = " · ".join(parts_en)

    # Pro 이상: 상세 분석 (economy/trade/travel)
    economy = None
    trade = None
    travel = None

    is_pro = user_plan in ("pro", "pro_plus")

    if is_pro and top_10:
        from backend.app.models.economic_data import CommodityPrice as CP2, MarketIndex as MI2, TradeBilateral as TB2, TravelAdvisory
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

        # ── 실제 데이터 조회 (배치 — oil_row는 위에서 이미 조회됨) ──
        # oil_row는 top_issues 배치에서 이미 조회 완료
        oil_str = f"${oil_row[0]:,.0f}({oil_row[1]:+.1f}%)" if oil_row else None

        # 금 (1 쿼리)
        gold_q = await db.execute(
            select(CP2.price_usd, CP2.change_pct)
            .where(CP2.symbol == "GOLD")
            .order_by(CP2.price_date.desc()).limit(1)
        )
        gold_row = gold_q.first()

        # 홈 국가 주가지수 (1 쿼리)
        home_idx_map = _HOME_INDEX_MAP
        home_idx_sym = home_idx_map.get(home)
        idx_str = None
        if home_idx_sym:
            idx_q = await db.execute(
                select(MI2.name, MI2.change_pct)
                .where(MI2.symbol == home_idx_sym)
                .order_by(MI2.index_date.desc()).limit(1)
            )
            idx_row = idx_q.first()
            if idx_row:
                idx_str = f"{idx_row[0]} {idx_row[1]:+.1f}%"

        # 주요 교역 파트너별 교역액 — 배치 조회 (1 쿼리)
        top_country_codes = list(top_countries.keys())[:5]
        trade_vols: dict[str, float] = {}
        if top_country_codes and home:
            tv_q = await db.execute(
                select(TB2.partner_code, TB2.total_trade_usd)
                .where(
                    TB2.reporter_code == home,
                    TB2.partner_code.in_(top_country_codes),
                    TB2.period_type == "A",
                )
                .order_by(TB2.period.desc())
            )
            for row in tv_q.fetchall():
                if row[0] not in trade_vols and row[1] and row[1] > 0:
                    trade_vols[row[0]] = row[1]

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

        # 교역 의존도 비율 계산 (분쟁국 vs 전체)
        total_conflict_trade = sum(trade_vols.values()) if trade_vols else 0

        # 경제 지표 조회 (인플레이션, 교역비중, 경상수지) — IN절 배치화
        from backend.app.models.economic_data import EconomicIndicator
        econ_extras: dict[str, float | None] = {}
        _IND_CODE_MAP = {
            "FP.CPI.TOTL.ZG": "inflation",
            "NE.TRD.GNFS.ZS": "trade_openness",
            "BN.CAB.XOKA.CD": "current_account",
        }
        if home:
            eq = await db.execute(
                select(
                    EconomicIndicator.indicator_code,
                    EconomicIndicator.value,
                )
                .where(
                    EconomicIndicator.country_code == home,
                    EconomicIndicator.indicator_code.in_(list(_IND_CODE_MAP.keys())),
                )
                .order_by(EconomicIndicator.indicator_code, EconomicIndicator.year.desc())
            )
            _seen_ind: set[str] = set()
            for row in eq.fetchall():
                ind_code = row[0]
                if ind_code not in _seen_ind:
                    _seen_ind.add(ind_code)
                    key = _IND_CODE_MAP.get(ind_code)
                    if key:
                        econ_extras[key] = row[1]

        if lang == "ko":
            display_home = "글로벌" if is_global else home
            # ── Economy: 구체적 수치 + 비자명적 분석 ──
            econ_parts = []
            if energy_risk and oil_row:
                price, chg = oil_row
                if chg > 0:
                    econ_parts.append(f"유가 ${price:,.0f}({chg:+.1f}%), 배럴당 $80+ 지속 시 정유·항공·물류 마진 압박 예상")
                else:
                    econ_parts.append(f"유가 ${price:,.0f}({chg:+.1f}%). 하락세지만 중동 리스크 프리미엄 상존")
            elif oil_str:
                econ_parts.append(f"유가 {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"금 ${gold_row[0]:,.0f}({gold_row[1]:+.1f}%) 안전자산 선호 확대, 리스크오프 심리 강화 신호")
            elif gold_row and gold_row[1] < -1.0:
                econ_parts.append(f"금 ${gold_row[0]:,.0f}({gold_row[1]:+.1f}%) 하락. 리스크 완화 또는 달러 강세 영향")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details:
                econ_parts.append(f"영향 섹터: {', '.join(sector_details[:3])}. 관련주 변동성 확대 구간")
            # 경제 지표 추가 인사이트
            inflation_val = econ_extras.get("inflation")
            trade_open_val = econ_extras.get("trade_openness")
            ca_val = econ_extras.get("current_account")
            if inflation_val and inflation_val > 5:
                econ_parts.append(f"인플레이션 {inflation_val:.1f}%, 원자재 상승 시 추가 물가 압력")
            if trade_open_val and trade_open_val > 80:
                econ_parts.append(f"교역/GDP {trade_open_val:.0f}%, 글로벌 공급망 교란에 높은 노출")
            if ca_val and ca_val < 0:
                econ_parts.append("경상수지 적자, 외환 유출 리스크")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"{display_home} 경제 직접 영향 제한적, 간접 파급 모니터링 중."

            # ── Trade: 의존도 비율 + 공급망 시사점 ──
            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{display_home}↔{top_tv[0]} 교역 {_fmt_usd(top_tv[1])}, 분쟁국 중 최대 노출 지점")
                if len(sorted_tv) > 1:
                    for c, v in sorted_tv[1:3]:
                        trade_parts.append(f"{display_home}↔{c} {_fmt_usd(v)} 교역 분쟁 영향권 내")
                if energy_risk and total_conflict_trade > 0:
                    trade_parts.append(f"에너지 수입선 다변화 불가 시 공급 차질 리스크. 대체 조달 소요 최소 2-4주")
            elif energy_risk:
                trade_parts.append("에너지 수입 의존국 불안정, 유가·가스 가격 연동 리스크 확대")
            if not trade_parts:
                trade_parts.append(f"{display_home} 직접 교역 리스크 제한적이나 글로벌 공급망 간접 파급 주시 필요")
            trade = ". ".join(trade_parts) + "."

            # ── Travel: 여행 경보 + 인접국 영향 ──
            travel_parts = []
            if lv4_count > 0:
                lv4_names_q = await db.execute(
                    select(TravelAdvisory.country_code)
                    .where(TravelAdvisory.level == 4, TravelAdvisory.country_code.in_(list(top_countries.keys())))
                )
                lv4_in_issues = [r[0] for r in lv4_names_q.all()]
                if lv4_in_issues:
                    travel_parts.append(f"이슈 관련 {len(lv4_in_issues)}개국 여행금지(Lv.4): {', '.join(lv4_in_issues[:4])}. 인접국 경유편 취소·감편 가능성")
                travel_parts.append(f"전 세계 {lv4_count}개국 여행금지 상태. 분쟁 확산 시 인접국 경보 상향 가능")
            if critical_count > 0:
                travel_parts.append(f"고영향 이슈 {critical_count}건 관련 항공편 변동·보험료 할증 주의")
            if not travel_parts:
                travel_parts.append("현재 주요 여행 제한 없음. 분쟁 지역 주변 경보 단계 변동 모니터링 중")
            travel = ". ".join(travel_parts) + "."
        else:
            display_home = "Global" if is_global else home
            # ── English: specific data + non-obvious insights ──
            econ_parts = []
            if energy_risk and oil_row:
                price, chg = oil_row
                if chg > 0:
                    econ_parts.append(f"Oil ${price:,.0f} ({chg:+.1f}%); sustained above $80/bbl pressures refinery, airline & logistics margins")
                else:
                    econ_parts.append(f"Oil ${price:,.0f} ({chg:+.1f}%). Declining, but geopolitical risk premium persists")
            elif oil_str:
                econ_parts.append(f"Oil {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"Gold ${gold_row[0]:,.0f} ({gold_row[1]:+.1f}%) rising; risk-off sentiment strengthening")
            elif gold_row and gold_row[1] < -1.0:
                econ_parts.append(f"Gold ${gold_row[0]:,.0f} ({gold_row[1]:+.1f}%) falling. Risk easing or dollar strength")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details:
                econ_parts.append(f"Exposed sectors: {', '.join(sector_details[:3])}. Elevated volatility expected")
            # Economic indicator insights
            inflation_val = econ_extras.get("inflation")
            trade_open_val = econ_extras.get("trade_openness")
            ca_val = econ_extras.get("current_account")
            if inflation_val and inflation_val > 5:
                econ_parts.append(f"Inflation {inflation_val:.1f}%; commodity spikes add further price pressure")
            if trade_open_val and trade_open_val > 80:
                econ_parts.append(f"Trade/GDP {trade_open_val:.0f}%, high exposure to global supply chain disruptions")
            if ca_val and ca_val < 0:
                econ_parts.append("Current account deficit, forex outflow risk")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"{display_home} economy: limited direct impact, monitoring indirect spillover."

            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{display_home}↔{top_tv[0]} trade at {_fmt_usd(top_tv[1])}, primary conflict exposure")
                if len(sorted_tv) > 1:
                    for c, v in sorted_tv[1:3]:
                        trade_parts.append(f"{display_home}↔{c} {_fmt_usd(v)} within conflict zone")
                if energy_risk and total_conflict_trade > 0:
                    trade_parts.append("Energy supply diversification lag 2-4 weeks if disrupted")
            elif energy_risk:
                trade_parts.append("Energy import dependency at risk; oil & gas price pass-through likely")
            if not trade_parts:
                trade_parts.append(f"Direct trade exposure for {display_home} limited; global supply chain spillover possible")
            trade = ". ".join(trade_parts) + "."

            travel_parts = []
            if lv4_count > 0:
                travel_parts.append(f"{lv4_count} countries at Do Not Travel (Lv.4). Adjacent transit routes may face cancellations")
            if critical_count > 0:
                travel_parts.append(f"{critical_count} high-impact issues. Flight disruptions & insurance surcharges possible")
            if not travel_parts:
                travel_parts.append("No major travel restrictions. Monitoring advisory escalation near conflict zones")
            travel = ". ".join(travel_parts) + "."

    # ── 병렬 조회: market_snapshot, trade_exposure, travel_advisories, risk_radar ──
    # 서로 독립적인 비동기 쿼리들을 asyncio.gather로 병렬 실행
    trade_home = home if home else "US"

    gather_results = await asyncio.gather(
        _get_market_snapshot(home, db),
        _get_trade_exposure(trade_home, db),
        _get_travel_advisories(home, scored[:10], is_pro, db),
        _compute_risk_radar(home, scored, sectors_data, oil_row, db, commodity_prices),
        return_exceptions=True,
    )

    # market_snapshot
    market_snapshot = None
    if isinstance(gather_results[0], Exception):
        logger.warning("market_snapshot_error", error=str(gather_results[0]))
    else:
        market_snapshot = gather_results[0]

    # trade_exposure
    trade_exposure = None
    if isinstance(gather_results[1], Exception):
        logger.warning("trade_exposure_error", error=str(gather_results[1]))
    else:
        trade_exposure_data = gather_results[1]
        if trade_exposure_data:
            if not is_pro:
                # Free: top 3 partners, dependency_pct only
                limited = []
                for p in trade_exposure_data["top_partners"][:3]:
                    limited.append({
                        "country_code": p["country_code"],
                        "trade_volume_usd": p["trade_volume_usd"],
                        "dependency_pct": p["dependency_pct"],
                        "export_usd": None,
                        "import_usd": None,
                        "trade_balance": None,
                    })
                trade_exposure = {
                    "top_partners": limited,
                    "total_trade_volume": trade_exposure_data["total_trade_volume"],
                }
            else:
                trade_exposure = trade_exposure_data

    # travel_advisories
    travel_advisories = []
    if isinstance(gather_results[2], Exception):
        logger.warning("travel_advisories_error", error=str(gather_results[2]))
    else:
        travel_advisories = gather_results[2] or []

    # risk_radar
    risk_radar = None
    if isinstance(gather_results[3], Exception):
        logger.warning("risk_radar_error", error=str(gather_results[3]))
    else:
        risk_radar_obj = gather_results[3]
        risk_radar = risk_radar_obj.model_dump() if risk_radar_obj else None

    # ── Impact Flow (동기 함수 — commodity_prices 재사용) ──
    impact_flow = None
    try:
        impact_flow_obj = _compute_impact_flow(scored, home, sectors_data, trade_map, oil_row, lang, commodity_prices)
        impact_flow = impact_flow_obj.model_dump() if impact_flow_obj else None
    except Exception as e:
        logger.warning("impact_flow_error", error=str(e))

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
        "risk_radar": risk_radar,
        "impact_flow": impact_flow,
    }

    # 6시간 캐시
    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=30 * 60)

    return ImpactSummaryOut(**response_data)


@router.get("/summary", response_model=ImpactSummaryOut)
async def get_impact_summary(
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    home_country: str | None = Query(None, description="홈 국가 코드 (빈 문자열=글로벌)"),
    lang: str | None = Query(None, description="응답 언어 (ko/en). 미지정 시 사용자 설정 사용"),
):
    """홀리스틱 종합 영향도 (모든 플랜, 미인증 시 free 기본값)."""
    if home_country is not None:
        home = home_country
    elif user:
        home = user.home_country or ""
    else:
        home = ""
    user_plan = (user.plan if user else None) or "free"
    # admin_plan_override 반영
    if user and getattr(user, "admin_plan_override", False) and user_plan == "free":
        user_plan = "pro"

    resolved_lang = lang
    if not resolved_lang and user:
        from backend.app.models.user import UserPreference
        pref_q = await db.execute(
            select(UserPreference.language).where(UserPreference.user_id == user.id)
        )
        pref_lang = pref_q.scalar_one_or_none()
        resolved_lang = pref_lang or "ko"
    elif not resolved_lang:
        resolved_lang = "en"

    return await _build_impact_summary(home, user_plan, resolved_lang, db)


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


def _brief_cache_key(cluster_id: str, home_country: str, lang: str = "ko") -> str:
    return f"impact:brief:{_CACHE_VERSION}:{cluster_id}:{home_country}:{lang}"


async def _generate_impact_brief(
    cluster: IssueCluster,
    home_country: str,
    lang: str,
    db: AsyncSession,
    commodity_prices: dict | None = None,
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

            # 원자재 컨텍스트 생성
            _commodity_context = ""
            _cp = commodity_prices or {}
            _ref = _get_commodity_ref(country_code, _cp, "en")
            if _ref:
                _commodity_context = f"\nRelevant commodity: {_ref[0]} ${_ref[1]:,.2f} ({_ref[2]:+.1f}%)"
            # 주요 원자재 시세 요약 (최대 5개)
            _key_commodities = []
            for _sym in ("WTI", "NATGAS", "WHEAT", "CORN", "GOLD"):
                if _sym in _cp:
                    _p, _c = _cp[_sym]
                    _key_commodities.append(f"{_sym}: ${_p:,.2f} ({_c:+.1f}%)")
            if _key_commodities:
                _commodity_context += "\nKey commodity prices: " + ", ".join(_key_commodities)

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
{_commodity_context}

Recent events:
{events_text}

Respond in {"Korean" if lang == "ko" else "English"} as JSON:
{{"economy": "2-3 sentences", "trade": "2-3 sentences", "travel": "2-3 sentences", "summary": "2-3 sentence brief covering key risks and their magnitude", "score": {impact_score}, "data_sources": ["World Bank", ...]}}

Note: The score should be close to {impact_score} (pre-calculated based on trade dependency and severity). You may adjust ±10 based on qualitative factors."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
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

    # 원자재 근거 문자열 (규칙 기반 fallback용)
    _cp = commodity_prices or {}
    _commodity_detail_ko = ""
    _commodity_detail_en = ""
    _cref = _get_commodity_ref(country_code, _cp, "ko")
    if _cref:
        _n, _pr, _ch, _s = _cref
        _ps = f"${_pr:,.0f}" if _pr >= 10 else f"${_pr:.2f}"
        _sign = "+" if _ch > 0 else ""
        _commodity_detail_ko = f" {_n} {_ps}({_sign}{_ch:.1f}%)."
    _cref_en = _get_commodity_ref(country_code, _cp, "en")
    if _cref_en:
        _n, _pr, _ch, _s = _cref_en
        _ps = f"${_pr:,.0f}" if _pr >= 10 else f"${_pr:.2f}"
        _sign = "+" if _ch > 0 else ""
        _commodity_detail_en = f" {_n.title()} {_ps} ({_sign}{_ch:.1f}%)."

    if lang == "ko":
        economy = f"{country_code} 지역 긴장도 {tension_score:.0f}/100({tension_label}). "
        if trade_vol_str:
            economy += f"양자 교역 규모 {trade_vol_str}. "
        economy += f"에너지·원자재 가격 변동 및 환율 영향 가능성."
        if _commodity_detail_ko:
            economy += _commodity_detail_ko

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

        summary = f"{cluster_title[:50]}. {home_country} 영향도 {score}/100"
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
    if _commodity_detail_en:
        economy += _commodity_detail_en

    trade = ""
    if sectors_str:
        trade = f"{home_country}'s {sectors_str} sectors exposed. "
    if trade_vol_str:
        trade += f"Trade volume {trade_vol_str}. Monitor supply chain disruptions."
    else:
        trade += "Low direct trade exposure; watch for indirect spillover."

    travel = f"Exercise caution (severity {severity}/100). "
    if tension_score >= 60:
        travel += "High likelihood of flight disruptions and transit restrictions."
    else:
        travel += "Check local advisories before traveling."

    summary = f"{cluster_title[:50]}. Impact on {home_country}: {score}/100"
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
    lang: str | None = Query(None, description="응답 언어 (ko/en). 미지정 시 사용자 설정 사용"),
    home_country: str | None = Query(None, description="분석 기준 국가 (ISO2). 미지정 시 사용자 설정 사용"),
):
    """이슈의 경제/무역/여행 영향 분석 (Pro 이상)"""
    # 사용자 언어 결정 (쿼리 파라미터 > DB 설정 > 기본값)
    resolved_lang = lang
    if not resolved_lang:
        from backend.app.models.user import UserPreference
        pref_q = await db.execute(
            select(UserPreference.language).where(UserPreference.user_id == user.id)
        )
        pref_lang = pref_q.scalar_one_or_none()
        resolved_lang = pref_lang or "ko"
    lang = resolved_lang

    # 기준 국가 결정 (쿼리 파라미터 > 사용자 설정 > 기본값)
    effective_home = home_country or user.home_country or "KR"

    # 캐시 확인
    redis = get_redis()
    cache_key = _brief_cache_key(cluster_id, effective_home, lang)
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

    # 원자재 가격 조회 (AI 컨텍스트용)
    from backend.app.models.economic_data import CommodityPrice
    _brief_cp_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(["WTI", "BRENT", "NATGAS", "WHEAT", "CORN", "GOLD", "BDRY"]))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )
    _brief_cp: dict[str, tuple[float, float]] = {}
    for _bcp in _brief_cp_q.scalars():
        if _bcp.symbol not in _brief_cp:
            _brief_cp[_bcp.symbol] = (_bcp.price_usd, _bcp.change_pct or 0)

    # AI 분석 생성
    brief = await _generate_impact_brief(cluster, effective_home, lang, db, _brief_cp)

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
    # v2 확장 필드 (nullable — 하위호환)
    trade_volume_usd: float | None = Field(None, description="Total bilateral trade USD millions")
    export_usd: float | None = Field(None, description="Export to affected USD millions")
    import_usd: float | None = Field(None, description="Import from affected USD millions")
    affected_countries: list[str] = Field(default_factory=list, description="Affected country codes")
    risk_summary: str = Field("", description="1-line risk summary")
    supply_disruption_weeks: str | None = Field(None, description="e.g. '2-4'")
    cost_increase_pct: str | None = Field(None, description="e.g. '+12-18%'")
    scenario_worst: str | None = None
    scenario_base: str | None = None
    scenario_best: str | None = None
    action_point: str | None = None


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
        "electronics": {"gdp_pct": 5.5, "key_partners": ["US", "CN", "VN", "JP", "IN"]},
        "manufacturing": {"gdp_pct": 25.0, "key_partners": ["CN", "US", "VN", "JP", "IN"]},
        "automotive": {"gdp_pct": 3.5, "key_partners": ["US", "CN", "IN", "DE"]},
        "agriculture": {"gdp_pct": 1.8, "key_partners": ["US", "AU", "BR", "UA", "RU"]},
        "shipping": {"gdp_pct": 2.1, "key_partners": ["CN", "JP", "US", "SG", "VN"]},
        "tourism": {"gdp_pct": 2.8, "key_partners": ["CN", "JP", "US", "TW", "TH"]},
    },
    "US": {
        "energy": {"gdp_pct": 5.8, "key_partners": ["CA", "SA", "MX", "RU", "IQ"]},
        "technology": {"gdp_pct": 8.2, "key_partners": ["CN", "TW", "KR", "JP", "IE"]},
        "semiconductor": {"gdp_pct": 2.5, "key_partners": ["TW", "KR", "JP", "CN", "NL"]},
        "manufacturing": {"gdp_pct": 11.0, "key_partners": ["CN", "MX", "CA", "DE", "JP"]},
        "shipping": {"gdp_pct": 2.8, "key_partners": ["CN", "JP", "KR", "DE", "GB"]},
        "automotive": {"gdp_pct": 3.0, "key_partners": ["MX", "CA", "JP", "DE", "KR"]},
        "agriculture": {"gdp_pct": 4.5, "key_partners": ["CN", "CA", "MX", "JP", "BR"]},
        "defense": {"gdp_pct": 3.4, "key_partners": ["GB", "AU", "JP", "KR", "IL"]},
        "tourism": {"gdp_pct": 2.6, "key_partners": ["MX", "CA", "GB", "JP", "CN"]},
    },
    "JP": {
        "energy": {"gdp_pct": 3.8, "key_partners": ["SA", "AE", "AU", "QA", "RU"]},
        "automotive": {"gdp_pct": 5.2, "key_partners": ["US", "CN", "TH", "ID", "DE"]},
        "electronics": {"gdp_pct": 4.1, "key_partners": ["CN", "US", "KR", "TW", "TH"]},
        "semiconductor": {"gdp_pct": 3.0, "key_partners": ["US", "TW", "CN", "KR", "NL"]},
        "manufacturing": {"gdp_pct": 20.0, "key_partners": ["US", "CN", "KR", "TH", "DE"]},
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
        "shipping": {"gdp_pct": 2.0, "key_partners": ["NL", "CN", "US", "FR", "PL"]},
        "electronics": {"gdp_pct": 3.2, "key_partners": ["CN", "US", "NL", "FR", "CZ"]},
        "agriculture": {"gdp_pct": 0.8, "key_partners": ["NL", "FR", "PL", "IT", "ES"]},
        "tourism": {"gdp_pct": 2.5, "key_partners": ["NL", "CH", "AT", "US", "GB"]},
    },
    "GB": {
        "energy": {"gdp_pct": 3.2, "key_partners": ["NO", "US", "NL", "QA", "SA"]},
        "finance": {"gdp_pct": 8.3, "key_partners": ["US", "DE", "FR", "NL", "JP"]},
        "technology": {"gdp_pct": 5.5, "key_partners": ["US", "DE", "IE", "NL", "CN"]},
        "manufacturing": {"gdp_pct": 9.0, "key_partners": ["US", "DE", "FR", "NL", "CN"]},
        "shipping": {"gdp_pct": 1.5, "key_partners": ["NL", "US", "DE", "FR", "CN"]},
        "agriculture": {"gdp_pct": 0.6, "key_partners": ["IE", "NL", "FR", "DE", "ES"]},
        "tourism": {"gdp_pct": 3.0, "key_partners": ["US", "FR", "DE", "IE", "ES"]},
    },
    "FR": {
        "energy": {"gdp_pct": 2.8, "key_partners": ["NO", "SA", "US", "RU", "NE"]},
        "automotive": {"gdp_pct": 2.5, "key_partners": ["DE", "ES", "IT", "GB", "BE"]},
        "manufacturing": {"gdp_pct": 10.0, "key_partners": ["DE", "US", "IT", "ES", "BE"]},
        "shipping": {"gdp_pct": 1.8, "key_partners": ["DE", "US", "CN", "NL", "IT"]},
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
    "ID": {  # 인도네시아
        "energy": {"gdp_pct": 3.5, "key_partners": ["SA", "AE", "MY", "NG", "IQ"]},
        "manufacturing": {"gdp_pct": 20.0, "key_partners": ["CN", "JP", "US", "KR", "TH"]},
        "agriculture": {"gdp_pct": 13.0, "key_partners": ["CN", "US", "IN", "JP", "MY"]},
        "mining": {"gdp_pct": 7.0, "key_partners": ["CN", "JP", "IN", "KR", "US"]},
        "tourism": {"gdp_pct": 4.5, "key_partners": ["MY", "SG", "AU", "CN", "JP"]},
    },
    "PH": {  # 필리핀
        "electronics": {"gdp_pct": 6.0, "key_partners": ["US", "CN", "JP", "HK", "SG"]},
        "manufacturing": {"gdp_pct": 18.0, "key_partners": ["US", "JP", "CN", "HK", "SG"]},
        "agriculture": {"gdp_pct": 9.0, "key_partners": ["US", "JP", "CN", "HK", "NL"]},
        "shipping": {"gdp_pct": 3.0, "key_partners": ["US", "CN", "JP", "SG", "HK"]},
        "tourism": {"gdp_pct": 5.5, "key_partners": ["KR", "US", "JP", "CN", "AU"]},
    },
    "PL": {  # 폴란드
        "manufacturing": {"gdp_pct": 18.0, "key_partners": ["DE", "FR", "GB", "CZ", "IT"]},
        "automotive": {"gdp_pct": 4.0, "key_partners": ["DE", "GB", "FR", "IT", "CZ"]},
        "agriculture": {"gdp_pct": 2.5, "key_partners": ["DE", "GB", "FR", "NL", "IT"]},
        "energy": {"gdp_pct": 4.0, "key_partners": ["DE", "NO", "US", "SA", "RU"]},
        "technology": {"gdp_pct": 5.0, "key_partners": ["DE", "US", "GB", "FR", "NL"]},
    },
    "EG": {  # 이집트
        "energy": {"gdp_pct": 6.0, "key_partners": ["IT", "US", "IN", "ES", "TR"]},
        "tourism": {"gdp_pct": 5.0, "key_partners": ["DE", "GB", "RU", "SA", "US"]},
        "agriculture": {"gdp_pct": 11.0, "key_partners": ["SA", "US", "IT", "TR", "LY"]},
        "shipping": {"gdp_pct": 3.5, "key_partners": ["SA", "US", "CN", "IN", "AE"]},
        "manufacturing": {"gdp_pct": 15.0, "key_partners": ["US", "SA", "TR", "IT", "DE"]},
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
_HOME_CURRENCIES: dict[str, list[str]] = {
    # DB에 수집되는 통화: AUD BRL CAD CNY EUR GBP IDR ILS INR JPY KRW MXN PHP PLN SGD THB TRY
    # 동아시아
    "KR": ["KRW", "JPY", "CNY", "EUR"],
    "JP": ["JPY", "KRW", "CNY", "EUR"],
    "CN": ["CNY", "JPY", "KRW", "EUR"],
    "TW": ["CNY", "JPY", "KRW", "EUR"],
    # 동남아
    "TH": ["THB", "CNY", "JPY", "KRW"],
    "VN": ["CNY", "JPY", "KRW", "THB"],
    "SG": ["SGD", "CNY", "JPY", "EUR"],
    "ID": ["IDR", "CNY", "JPY", "SGD"],
    "PH": ["PHP", "CNY", "JPY", "SGD"],
    # 남아시아
    "IN": ["INR", "CNY", "JPY", "EUR"],
    # 북미
    "US": ["EUR", "JPY", "GBP", "CNY"],
    "CA": ["CAD", "EUR", "JPY", "CNY"],
    "MX": ["MXN", "EUR", "CAD", "CNY"],
    # 유럽
    "DE": ["EUR", "GBP", "JPY", "CNY"],
    "GB": ["GBP", "EUR", "JPY", "CNY"],
    "FR": ["EUR", "GBP", "JPY", "CNY"],
    "PL": ["PLN", "EUR", "GBP", "CNY"],
    "RU": ["CNY", "EUR", "INR", "TRY"],
    "TR": ["TRY", "EUR", "GBP", "CNY"],
    # 중동
    "SA": ["EUR", "CNY", "INR", "GBP"],
    "AE": ["EUR", "CNY", "INR", "GBP"],
    "IL": ["ILS", "EUR", "GBP", "CNY"],
    "EG": ["EUR", "CNY", "GBP", "INR"],
    # 오세아니아
    "AU": ["AUD", "CNY", "JPY", "EUR"],
    # 남미
    "BR": ["BRL", "EUR", "CNY", "MXN"],
}

# ── 국가→관련 원자재 매핑 (reason/summary 다양화용) ──
_COUNTRY_COMMODITY_MAP: dict[str, dict] = {
    # 곡물 수출국
    "UA": {"symbols": ["WHEAT"], "ko": "밀", "en": "wheat"},
    "RU": {"symbols": ["WHEAT", "NATGAS"], "ko": "밀·가스", "en": "wheat & gas"},
    "BR": {"symbols": ["SOYBEAN", "CORN"], "ko": "대두·옥수수", "en": "soybean & corn"},
    "AR": {"symbols": ["SOYBEAN", "WHEAT"], "ko": "대두·밀", "en": "soybean & wheat"},
    "IN": {"symbols": ["RICE"], "ko": "쌀", "en": "rice"},
    "MM": {"symbols": ["RICE"], "ko": "쌀", "en": "rice"},
    "TH": {"symbols": ["RICE"], "ko": "쌀", "en": "rice"},
    "VN": {"symbols": ["RICE"], "ko": "쌀", "en": "rice"},
    "AU": {"symbols": ["WHEAT", "CORN"], "ko": "밀·옥수수", "en": "wheat & corn"},
    "CA": {"symbols": ["WHEAT", "WTI"], "ko": "밀·원유", "en": "wheat & oil"},
    # 산유국 (기존 oil_row 보강)
    "SA": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "AE": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "IQ": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "KW": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "IR": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "LY": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    # 천연가스 핵심국
    "QA": {"symbols": ["NATGAS"], "ko": "천연가스", "en": "natural gas"},
    "NO": {"symbols": ["NATGAS"], "ko": "천연가스", "en": "natural gas"},
    # 해운 허브
    "EG": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
    "PA": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
    "YE": {"symbols": ["BDRY", "WTI"], "ko": "해운·유가", "en": "shipping & oil"},
    "SO": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
}


def _get_commodity_ref(
    cc: str, commodity_prices: dict | None, lang: str,
) -> tuple[str, float, float, str] | None:
    """국가 코드에 매핑된 원자재 가격 참조를 반환. (name, price, change_pct, symbol) or None"""
    if not commodity_prices or cc not in _COUNTRY_COMMODITY_MAP:
        return None
    meta = _COUNTRY_COMMODITY_MAP[cc]
    name = meta["ko"] if lang == "ko" else meta["en"]
    for sym in meta["symbols"]:
        if sym in commodity_prices:
            price, change = commodity_prices[sym]
            return (name, price, change, sym)
    return None


def _format_commodity_reason(name: str, price: float, change: float, sym: str, h_name: str, lang: str) -> str:
    """원자재 참조를 reason 문장으로 변환."""
    sign = "+" if change > 0 else ""
    price_str = f"${price:,.0f}" if price >= 10 else f"${price:.2f}"
    if lang == "ko":
        if sym in ("WHEAT", "CORN", "SOYBEAN", "RICE"):
            return f"{name} {price_str}({sign}{change:.1f}%), {h_name} 식료품 가격 상승 압력"
        elif sym == "BDRY":
            return f"해운지수 {price_str}({sign}{change:.1f}%), {h_name} 물류비 영향"
        elif sym == "NATGAS":
            return f"천연가스 {price_str}({sign}{change:.1f}%), {h_name} 에너지 비용 상승"
        else:
            return f"유가 {price_str}({sign}{change:.1f}%), {h_name} 에너지 비용 직접 상승 압력"
    else:
        if sym in ("WHEAT", "CORN", "SOYBEAN", "RICE"):
            return f"{name.title()} {price_str} ({sign}{change:.1f}%), food cost pressure for {h_name}"
        elif sym == "BDRY":
            return f"Shipping index {price_str} ({sign}{change:.1f}%), logistics cost impact on {h_name}"
        elif sym == "NATGAS":
            return f"Natural gas {price_str} ({sign}{change:.1f}%), energy cost pressure for {h_name}"
        else:
            return f"Oil {price_str} ({sign}{change:.1f}%), rising energy costs for {h_name}"


def _get_relevant_symbols(cc: str, topic: str, commodity_prices: dict | None = None) -> list[str]:
    """SmartSummaryCard 마켓칩에 표시할 원자재 심볼 추천 (최대 3개)."""
    symbols: list[str] = []
    if cc in _COUNTRY_COMMODITY_MAP:
        symbols.extend(_COUNTRY_COMMODITY_MAP[cc]["symbols"])
    if topic in ("conflict", "terror") and "GOLD" not in symbols:
        symbols.append("GOLD")
    if topic in ("conflict", "terror", "military") and "WTI" not in symbols:
        symbols.append("WTI")
    if not symbols:
        symbols = ["WTI"]
    # 실제 가격 데이터가 있는 것만 필터
    if commodity_prices:
        symbols = [s for s in symbols if s in commodity_prices] or symbols
    seen: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.append(s)
    return seen[:3]


def _build_reason_sync(
    cluster,
    home_country: str,
    lang: str,
    sectors_data: dict,
    trade_map: dict[str, float],
    oil_row,
    commodity_prices: dict | None = None,
) -> str:
    """동기 함수: 배치 조회 결과로 reason 생성 (DB 호출 없음)."""
    cc = cluster.country_code or ""
    topic = cluster.topic or "unknown"
    severity = cluster.severity or 0
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])

    affected_sectors = []
    for sector, info in sectors_data.items():
        if cc in info.get("key_partners", []):
            affected_sectors.append((labels.get(sector, sector), info.get("gdp_pct", 0)))
    affected_sectors.sort(key=lambda x: -x[1])

    trade_vol = trade_map.get(cc)
    trade_str = ""
    if trade_vol and trade_vol > 0:
        if trade_vol >= 1e9:
            trade_str = f"${trade_vol / 1e9:.1f}B"
        elif trade_vol >= 1e6:
            trade_str = f"${trade_vol / 1e6:.0f}M"

    # 원자재 참조: 국가별 매핑 (유가 + 곡물 + 해운 + 가스)
    oil_price = None
    if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY"):
        if oil_row:
            oil_price = (oil_row[0], oil_row[1])

    commodity_ref = _get_commodity_ref(cc, commodity_prices, lang)

    h_name = _country_name(home_country, lang)
    c_name = _country_name(cc, lang)

    if lang == "ko":
        # 원자재 매핑이 있으면 우선 사용 (유가 외: 곡물/해운/가스)
        if commodity_ref and commodity_ref[3] not in ("WTI", "BRENT"):
            reason = _format_commodity_reason(*commodity_ref, h_name, lang)
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            reason = f"{h_name}↔{c_name} 교역 {trade_str}, {top_sector}(GDP {gdp}%) 공급망에 직접 영향"
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {h_name} {top_sector} 비용 직접 상승 압력"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {h_name} 에너지(GDP {gdp}%) 비용 상승"
            elif len(affected_sectors) >= 2:
                reason = f"{h_name} {affected_sectors[0][0]}(GDP {affected_sectors[0][1]}%)·{affected_sectors[1][0]} 분야 공급망 리스크"
            else:
                reason = f"{h_name} {top_sector}(GDP {gdp}%) 분야에 직접 영향"
        elif trade_str:
            reason = f"{h_name}↔{c_name} 교역 {trade_str}, 교역 관계 통한 간접 파급"
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
        if commodity_ref and commodity_ref[3] not in ("WTI", "BRENT"):
            reason = _format_commodity_reason(*commodity_ref, h_name, lang)
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            reason = f"{h_name}↔{c_name} trade {trade_str}, direct {top_sector} (GDP {gdp}%) supply chain exposure"
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), rising {top_sector} costs for {h_name}"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), {h_name} energy (GDP {gdp}%) cost pressure"
            elif len(affected_sectors) >= 2:
                reason = f"{h_name} {affected_sectors[0][0]} (GDP {affected_sectors[0][1]}%) & {affected_sectors[1][0]} supply chain risk"
            else:
                reason = f"Direct impact on {h_name}'s {top_sector} sector (GDP {gdp}%)"
        elif trade_str:
            reason = f"{h_name}↔{c_name} trade {trade_str}, indirect spillover via trade links"
        elif severity >= 70:
            reason = "High-intensity crisis causing global supply chain and market instability"
        elif topic == "sanctions":
            reason = "Sanctions expansion may disrupt raw material and component supply"
        elif topic == "disaster":
            reason = "Natural disaster causing logistics and manufacturing disruptions"
        else:
            reason = "Increased market uncertainty from geopolitical developments"

    return reason


def _build_smart_summary(cluster, home_country: str, lang: str, sectors_data: dict, trade_map: dict, oil_row, commodity_prices: dict | None = None) -> dict:
    """3줄 Smart Summary: what/so_what/when 생성"""
    cc = cluster.country_code or ""
    topic = cluster.topic or "unknown"
    severity = cluster.severity or 0
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    h_name = _country_name(home_country, lang)
    c_name = _country_name(cc, lang)

    # Affected sectors
    affected_sectors = []
    for sector, info in sectors_data.items():
        if cc in info.get("key_partners", []):
            affected_sectors.append((labels.get(sector, sector), info.get("gdp_pct", 0)))
    affected_sectors.sort(key=lambda x: -x[1])

    trade_vol = trade_map.get(cc)
    trade_str = ""
    if trade_vol and trade_vol > 0:
        if trade_vol >= 1e9:
            trade_str = f"${trade_vol / 1e9:.1f}B"
        elif trade_vol >= 1e6:
            trade_str = f"${trade_vol / 1e6:.0f}M"

    title = cluster.title_ko if lang == "ko" and cluster.title_ko else cluster.title or ""
    title = title[:60]

    # what_line
    if lang == "ko":
        what_line = title
    else:
        what_line = (cluster.title or title)[:60]

    # so_what_line — 원자재 매핑 우선, 유가 폴백
    oil_price = None
    if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY"):
        if oil_row:
            oil_price = (oil_row[0], oil_row[1])

    commodity_ref = _get_commodity_ref(cc, commodity_prices, lang)

    if lang == "ko":
        if commodity_ref and commodity_ref[3] not in ("WTI", "BRENT"):
            so_what_line = _format_commodity_reason(*commodity_ref, h_name, lang)
        elif oil_price:
            so_what_line = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), 가스비·물류비 상승 압력"
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name}과 교역 {trade_str}, {top_sector} 수입품 가격 상승 예상"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name} 관련 {top_sector}(GDP {gdp}%) 변동성 확대"
        else:
            so_what_line = _build_reason_sync(cluster, home_country, lang, sectors_data, trade_map, oil_row, commodity_prices)
    else:
        if commodity_ref and commodity_ref[3] not in ("WTI", "BRENT"):
            so_what_line = _format_commodity_reason(*commodity_ref, h_name, lang)
        elif oil_price:
            so_what_line = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), gas & logistics cost pressure"
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"Trade with {c_name} {trade_str}, {top_sector} import prices may rise"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name}-linked {top_sector} (GDP {gdp}%), volatility expected"
        else:
            so_what_line = _build_reason_sync(cluster, home_country, lang, sectors_data, trade_map, oil_row, commodity_prices)

    # when_line
    if lang == "ko":
        if severity >= 80 and topic in ("conflict", "terror"):
            when_line = "즉각적. 시장 이미 반영 중"
        elif severity >= 60:
            when_line = "1-2주 내 공급망 영향"
        elif severity >= 40:
            when_line = "1-3개월 모니터링 필요"
        else:
            when_line = "간접 영향. 추이 관찰"
    else:
        if severity >= 80 and topic in ("conflict", "terror"):
            when_line = "Immediate. Markets pricing in"
        elif severity >= 60:
            when_line = "Supply chain impact in 1-2 weeks"
        elif severity >= 40:
            when_line = "Monitor over 1-3 months"
        else:
            when_line = "Indirect. Monitoring trend"

    # relevant_commodities: SmartSummaryCard 마켓칩용
    rel_syms = _get_relevant_symbols(cc, topic, commodity_prices)

    return {"what_line": what_line, "so_what_line": so_what_line, "when_line": when_line, "relevant_commodities": rel_syms}


async def _compute_risk_radar(home: str, scored: list, sectors_data: dict, oil_row, db, commodity_prices: dict | None = None) -> RiskRadarOut | None:
    """Risk Radar 5축 계산 — 원자재 가격 변동 반영"""
    if not scored:
        return None

    from backend.app.models.tension_index import TensionIndex
    from backend.app.models.economic_data import MarketIndex

    _cp = commodity_prices or {}

    # Current values
    conflict_clusters = [(c, s) for c, s in scored if (c.topic or "") in ("conflict", "terror", "coup")]
    military_score = 0
    if conflict_clusters:
        avg_sev = sum(c.severity or 0 for c, _ in conflict_clusters) / len(conflict_clusters)
        military_score = min(100, avg_sev * 0.8 + len(conflict_clusters) * 3)

    energy_data = sectors_data.get("energy", {})
    energy_gdp = energy_data.get("gdp_pct", 3.0)
    oil_change = abs(oil_row[1]) if oil_row else 0
    energy_partners = set(energy_data.get("key_partners", []))
    energy_issues = sum(1 for c, _ in scored[:20] if (c.country_code or "") in energy_partners)
    # 천연가스 변동률도 에너지 스코어에 반영
    gas_change = abs(_cp["NATGAS"][1]) if "NATGAS" in _cp else 0
    energy_score = min(100, energy_gdp * 3 + oil_change * 5 + gas_change * 3 + energy_issues * 10)

    trade_issues = sum(1 for c, _ in scored[:20] if any(
        (c.country_code or "") in info.get("key_partners", [])
        for info in sectors_data.values()
    ))
    trade_score = min(100, trade_issues * 8 + len(scored[:20]) * 2)

    agri_data = sectors_data.get("agriculture", {})
    agri_gdp = agri_data.get("gdp_pct", 5.0)
    agri_partners = set(agri_data.get("key_partners", []))
    agri_issues = sum(1 for c, _ in scored[:20] if (c.country_code or "") in agri_partners)
    # 곡물 가격 변동률을 food_score에 반영
    grain_volatility = 0.0
    grain_count = 0
    for _gs in ("WHEAT", "CORN", "SOYBEAN", "RICE"):
        if _gs in _cp:
            grain_volatility += abs(_cp[_gs][1])
            grain_count += 1
    if grain_count > 0:
        grain_volatility /= grain_count
    food_score = min(100, agri_gdp * 2 + agri_issues * 15 + grain_volatility * 3)

    # Finance: market index change
    try:
        home_idx_map = _HOME_INDEX_MAP
        idx_sym = home_idx_map.get(home)
        finance_score = 30  # default
        if idx_sym:
            idx_q = await db.execute(
                select(MarketIndex.change_pct)
                .where(MarketIndex.symbol == idx_sym)
                .order_by(MarketIndex.index_date.desc())
                .limit(1)
            )
            idx_change = idx_q.scalar_one_or_none()
            if idx_change is not None:
                finance_score = min(100, abs(idx_change) * 10 + len(conflict_clusters) * 5)
    except Exception:
        finance_score = 30

    # Prev values (7 days ago — simplified: use 70% of current as approximation)
    # In production, you'd query 7-day-old tension_index
    prev_factor = 0.85  # approximate previous week
    prev_military = round(military_score * prev_factor, 1)
    prev_energy = round(energy_score * prev_factor, 1)
    prev_trade = round(trade_score * prev_factor, 1)
    prev_food = round(food_score * prev_factor, 1)
    prev_finance = round(finance_score * prev_factor, 1)

    axes = [
        RiskRadarAxis(axis="military", value=round(military_score, 1), prev_value=prev_military, label_ko="군사", label_en="Military"),
        RiskRadarAxis(axis="energy", value=round(energy_score, 1), prev_value=prev_energy, label_ko="에너지", label_en="Energy"),
        RiskRadarAxis(axis="trade", value=round(trade_score, 1), prev_value=prev_trade, label_ko="무역", label_en="Trade"),
        RiskRadarAxis(axis="food", value=round(food_score, 1), prev_value=prev_food, label_ko="식량", label_en="Food"),
        RiskRadarAxis(axis="finance", value=round(finance_score, 1), prev_value=prev_finance, label_ko="금융", label_en="Finance"),
    ]

    current_avg = sum(a.value for a in axes) / 5
    prev_avg = sum(a.prev_value for a in axes) / 5
    if current_avg > prev_avg + 3:
        trend = "deteriorating"
    elif current_avg < prev_avg - 3:
        trend = "improving"
    else:
        trend = "stable"

    return RiskRadarOut(axes=axes, overall_trend=trend)


def _compute_impact_flow(scored: list, home: str, sectors_data: dict, trade_map: dict, oil_row, lang: str, commodity_prices: dict | None = None) -> ImpactFlowOut | None:
    """Impact Flow Sankey 3단 데이터"""
    if not scored:
        return None

    # 글로벌 합산 sectors (fallback용으로도 사용)
    def _build_merged_sectors() -> dict:
        merged: dict[str, dict] = {}
        for _cc, country_sectors in SECTOR_DATA.items():
            for sector, info in country_sectors.items():
                if sector not in merged:
                    merged[sector] = {"gdp_pct": info["gdp_pct"], "key_partners": list(info.get("key_partners", []))}
                else:
                    for p in info.get("key_partners", []):
                        if p not in merged[sector]["key_partners"]:
                            merged[sector]["key_partners"].append(p)
        return merged

    if not home:
        sectors_data = _build_merged_sectors()

    # 토픽 → 관련 섹터 매핑 (key_partners 매칭 실패 시 fallback)
    _TOPIC_SECTOR_MAP: dict[str, list[str]] = {
        "conflict": ["energy", "shipping"],
        "terror": ["energy", "shipping", "tourism"],
        "military": ["energy", "shipping", "defense"],
        "economy": ["energy", "manufacturing", "shipping"],
        "trade": ["shipping", "manufacturing", "semiconductor"],
        "cyber": ["technology", "semiconductor", "electronics"],
        "diplomacy": ["energy", "shipping"],
        "sanctions": ["energy", "shipping", "manufacturing"],
        "humanitarian": ["agriculture"],
        "nuclear": ["energy", "defense"],
    }

    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    nodes = []
    links = []
    seen_commodities = set()

    def _add_sector_link(node_id: str, sector: str, severity: int, gdp_pct: float):
        """섹터 노드 + 링크 추가 (중복 방지)"""
        if sector not in seen_commodities:
            seen_commodities.add(sector)
            nodes.append(ImpactFlowNode(
                id=sector, label=labels.get(sector, sector),
                color="#f59e0b", category="commodity"
            ))
        link_value = round(severity * gdp_pct / 100, 2)
        if link_value > 0:
            links.append(ImpactFlowLink(source=node_id, target=sector, value=max(1, link_value)))

    top3 = scored[:3]
    for idx, (c, impact) in enumerate(top3):
        cc = c.country_code or ""
        severity = c.severity or 0
        topic = c.topic or "unknown"
        title = c.title_ko if lang == "ko" and c.title_ko else c.title or f"Issue {idx+1}"
        title = title[:20]
        node_id = f"c{idx}"
        nodes.append(ImpactFlowNode(
            id=node_id, label=title, color="#dc2626", category="conflict",
            cluster_id=str(c.id), country_codes=[cc] if cc else [],
        ))

        linked = False
        # 1차: key_partners 매칭 (이슈 국가가 기준 국가의 교역 파트너일 때)
        if cc != home:
            for sector, info in sectors_data.items():
                if cc in info.get("key_partners", []):
                    _add_sector_link(node_id, sector, severity, info.get("gdp_pct", 1))
                    linked = True

        # 2차: 이슈 국가가 기준 국가 자체이거나 key_partners에 없을 때 → 토픽 기반 연결
        if not linked:
            topic_sectors = _TOPIC_SECTOR_MAP.get(topic, ["energy", "shipping"])
            for sector in topic_sectors:
                if sector in sectors_data:
                    _add_sector_link(node_id, sector, severity, sectors_data[sector].get("gdp_pct", 1))
                    linked = True

        # 3차: 아직도 없으면 → 가장 큰 GDP 섹터에 연결
        if not linked and sectors_data:
            biggest = max(sectors_data.items(), key=lambda x: x[1].get("gdp_pct", 0))
            _add_sector_link(node_id, biggest[0], severity, biggest[1].get("gdp_pct", 1))

    # Right column: impact categories — 실제 데이터 기반 라벨
    oil_change = oil_row[1] if oil_row else 0
    oil_price = oil_row[0] if oil_row else 0

    # 영향받는 교역 총액 계산
    affected_ccs = {c.country_code for c, _ in top3 if c.country_code}
    affected_trade = sum(trade_map.get(cc, 0) for cc in affected_ccs)

    # sector → impact categories (1:다 — 현실적 교차 연결)
    _SECTOR_IMPACTS: dict[str, list[str]] = {
        "energy":        ["energy_cost", "gas_bill", "shipping_cost"],   # 에너지 → 에너지비 + 가스요금 + 물류비
        "agriculture":   ["food_cost"],
        "shipping":      ["shipping_cost", "food_cost"],        # 해운 → 물류비 + 식료품
        "semiconductor": ["electronics_cost"],
        "electronics":   ["electronics_cost"],
        "technology":    ["electronics_cost"],
        "manufacturing": ["mfg_cost", "electronics_cost"],      # 제조 → 제조원가 + 전자제품
        "mining":        ["energy_cost", "mfg_cost", "safe_haven"],  # 광업 → 에너지 + 제조원가 + 안전자산
        "finance":       ["safe_haven", "energy_cost"],         # 금융 → 안전자산 + 에너지비
        "construction":  ["mfg_cost"],                          # 건설 → 제조원가
        "automotive":    ["auto_cost"],
        "tourism":       ["travel_cost"],
        "defense":       ["energy_cost"],
    }

    # seen_commodities에서 필요한 impact ID + 연결 섹터 수집
    impact_sources: dict[str, list[str]] = {}   # imp_id → [sector_ids that link to it]
    for sector_id in seen_commodities:
        for imp_id in _SECTOR_IMPACTS.get(sector_id, ["inflation"]):
            impact_sources.setdefault(imp_id, []).append(sector_id)

    if not impact_sources:
        impact_sources["inflation"] = list(seen_commodities) if seen_commodities else ["energy"]

    # impact 라벨 생성 함수 — 2줄: label(카테고리) + sub_label(실시간 가격)
    _cp = commodity_prices or {}

    # impact_id → (카테고리 라벨 ko/en, 대표 상품 symbol, 상품명 ko/en)
    _IMPACT_META: dict[str, dict] = {
        "energy_cost":      {"ko": "에너지", "en": "Energy", "symbols": ["NATGAS", "WTI"], "name_ko": ["천연가스", "유가"], "name_en": ["NatGas", "Oil"]},
        "gas_bill":         {"ko": "가스요금", "en": "Gas Bill", "symbols": ["NATGAS"], "name_ko": ["천연가스"], "name_en": ["NatGas"]},
        "food_cost":        {"ko": "식료품", "en": "Food", "symbols": ["WHEAT", "CORN"], "name_ko": ["밀", "옥수수"], "name_en": ["Wheat", "Corn"]},
        "shipping_cost":    {"ko": "물류비", "en": "Logistics", "symbols": ["BDRY", "WTI"], "name_ko": ["해운", "유가"], "name_en": ["Shipping", "Oil"]},
        "safe_haven":       {"ko": "안전자산", "en": "Safe Haven", "symbols": ["GOLD", "SILVER"], "name_ko": ["금", "은"], "name_en": ["Gold", "Silver"]},
        "electronics_cost": {"ko": "전자제품", "en": "Electronics", "symbols": ["WTI"], "name_ko": ["유가"], "name_en": ["Oil"]},
        "auto_cost":        {"ko": "자동차", "en": "Auto", "symbols": ["WTI"], "name_ko": ["유가"], "name_en": ["Oil"]},
        "mfg_cost":         {"ko": "제조 원가", "en": "Manufacturing", "symbols": ["WTI"], "name_ko": ["유가"], "name_en": ["Oil"]},
        "travel_cost":      {"ko": "여행 경비", "en": "Travel", "symbols": ["JET_FUEL", "WTI"], "name_ko": ["항공유", "유가"], "name_en": ["JetFuel", "Oil"]},
        "inflation":        {"ko": "물가 상승", "en": "Inflation", "symbols": ["WTI"], "name_ko": ["유가"], "name_en": ["Oil"]},
    }

    def _impact_label_2line(imp_id: str) -> tuple[str, str | None]:
        """Returns (label, sub_label). sub_label에 실시간 가격 데이터."""
        meta = _IMPACT_META.get(imp_id)
        if not meta:
            return ("영향" if lang == "ko" else "Impact", None)
        label = meta["ko"] if lang == "ko" else meta["en"]

        # 대표 상품에서 가격 데이터 찾기 (첫번째 매칭)
        for i, sym in enumerate(meta["symbols"]):
            if sym in _cp:
                price, chg = _cp[sym]
                name = meta["name_ko"][i] if lang == "ko" else meta["name_en"][i]
                sign = "+" if chg > 0 else ""
                arrow = "↑" if chg > 0 else "↓" if chg < 0 else ""
                sub = f"{name} ${price:,.1f} {sign}{chg:.1f}%{arrow}" if price >= 10 else f"{name} ${price:.2f} {sign}{chg:.1f}%{arrow}"
                return (label, sub)

        # 가격 데이터 없으면 기존 방식 fallback
        return (label, None)

    # impact 노드 + 링크 생성
    for imp_id, source_sectors in impact_sources.items():
        lbl, sub_lbl = _impact_label_2line(imp_id)
        nodes.append(ImpactFlowNode(id=imp_id, label=lbl, sub_label=sub_lbl, color="#3b82f6", category="impact"))
        for sid in source_sectors:
            gdp = sectors_data.get(sid, {}).get("gdp_pct", 1)
            link_val = max(1, round(gdp * 2))
            links.append(ImpactFlowLink(source=sid, target=imp_id, value=link_val))

    if not nodes or not links:
        return None
    return ImpactFlowOut(nodes=nodes, links=links)


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
    h_name = _country_name(home_country, lang)
    c_name = _country_name(cc, lang)
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
            reason = f"{h_name}↔{c_name} 교역 {trade_str}, {top_sector}(GDP {gdp}%) 공급망에 직접 영향"
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {h_name} {top_sector} 비용 직접 상승 압력"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), {h_name} 에너지(GDP {gdp}%) 비용 상승"
            elif len(affected_sectors) >= 2:
                reason = f"{h_name} {affected_sectors[0][0]}(GDP {affected_sectors[0][1]}%)·{affected_sectors[1][0]} 분야 공급망 리스크"
            else:
                reason = f"{h_name} {top_sector}(GDP {gdp}%) 분야에 직접 영향"
        elif trade_str:
            reason = f"{h_name}↔{c_name} 교역 {trade_str}, 교역 관계 통한 간접 파급"
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
            reason = f"{h_name}↔{c_name} trade {trade_str}, direct {top_sector} (GDP {gdp}%) supply chain exposure"
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), rising {top_sector} costs for {h_name}"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            if oil_price:
                reason = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), {h_name} energy (GDP {gdp}%) cost pressure"
            elif len(affected_sectors) >= 2:
                reason = f"{h_name} {affected_sectors[0][0]} (GDP {affected_sectors[0][1]}%) & {affected_sectors[1][0]} supply chain risk"
            else:
                reason = f"Direct impact on {h_name}'s {top_sector} sector (GDP {gdp}%)"
        elif trade_str:
            reason = f"{h_name}↔{c_name} trade {trade_str}, indirect spillover via trade links"
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
    """시장 동향 스냅샷: 원자재 + 환율 + 주가지수 (배치 조회)"""
    from backend.app.models.economic_data import CommodityPrice, MarketIndex, ExchangeRate

    commodities = []
    indices = []
    exchange_rates = []

    # 1) 원자재: 국가별 관심 심볼 (DISTINCT ON)
    _COMMODITY_BY_HOME: dict[str, list[str]] = {
        # 동아시아 — 에너지 수입 의존 + 해운
        "KR": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT", "BDRY"],
        "JP": ["WTI", "BRENT", "GOLD", "RICE", "NATGAS", "BDRY"],
        "CN": ["WTI", "BRENT", "GOLD", "SOYBEAN", "WHEAT", "NATGAS"],
        "TW": ["WTI", "BRENT", "GOLD", "NATGAS", "BDRY"],
        # 동남아 — 쌀 + 에너지
        "TH": ["WTI", "GOLD", "RICE", "NATGAS", "BDRY"],
        "VN": ["WTI", "GOLD", "RICE", "NATGAS", "BDRY"],
        "SG": ["WTI", "BRENT", "GOLD", "NATGAS", "BDRY"],
        "ID": ["WTI", "GOLD", "RICE", "NATGAS", "CORN"],
        "PH": ["WTI", "GOLD", "RICE", "WHEAT", "BDRY"],
        # 남아시아
        "IN": ["WTI", "BRENT", "GOLD", "RICE", "WHEAT", "NATGAS"],
        # 북미 — 곡물 수출국
        "US": ["WTI", "BRENT", "GOLD", "NATGAS", "CORN", "SOYBEAN"],
        "CA": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "MX": ["WTI", "BRENT", "GOLD", "CORN", "SILVER"],
        # 유럽 — 가스 의존
        "DE": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "GB": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "FR": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "PL": ["WTI", "NATGAS", "GOLD", "WHEAT", "CORN"],
        "RU": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "TR": ["WTI", "BRENT", "GOLD", "WHEAT", "NATGAS"],
        # 중동 — 원유 생산국
        "SA": ["WTI", "BRENT", "GOLD", "NATGAS", "SILVER"],
        "AE": ["WTI", "BRENT", "GOLD", "NATGAS", "SILVER"],
        "IL": ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"],
        "EG": ["WTI", "BRENT", "GOLD", "WHEAT", "BDRY"],
        # 오세아니아 — 자원 수출국
        "AU": ["WTI", "GOLD", "WHEAT", "CORN", "NATGAS"],
        # 남미 — 곡물·자원
        "BR": ["WTI", "GOLD", "SOYBEAN", "CORN", "SILVER"],
    }
    _commodity_symbols = _COMMODITY_BY_HOME.get(home_country, ["WTI", "BRENT", "GOLD", "NATGAS", "WHEAT"])
    commodity_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(_commodity_symbols))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )
    for row in commodity_q.scalars().all():
        commodities.append({
            "symbol": row.symbol,
            "name": row.name,
            "price_usd": row.price_usd,
            "change_pct": row.change_pct,
        })

    # 2) 주가지수: 1 배치 쿼리
    index_q = await db.execute(
        select(MarketIndex)
        .distinct(MarketIndex.symbol)
        .where(MarketIndex.symbol.in_(list(_HOME_INDEX_MAP.values())))
        .order_by(MarketIndex.symbol, MarketIndex.index_date.desc())
    )
    for row in index_q.scalars().all():
        indices.append({
            "symbol": row.symbol,
            "name": row.name,
            "value": row.value,
            "change_pct": row.change_pct,
            "currency": row.currency,
        })

    # 3) 환율: 배치 쿼리 — 각 통화별 최신 2행을 한번에 조회 (N+1 해결)
    target_currencies = _HOME_CURRENCIES.get(home_country, ["EUR", "JPY", "GBP", "CNY"])
    rate_q = await db.execute(
        select(
            ExchangeRate.target_currency,
            ExchangeRate.rate,
            ExchangeRate.rate_date,
        )
        .where(
            ExchangeRate.base_currency == "USD",
            ExchangeRate.target_currency.in_(target_currencies),
        )
        .order_by(ExchangeRate.target_currency, ExchangeRate.rate_date.desc())
    )
    all_rate_rows = rate_q.fetchall()

    # 각 통화별 최신 2행을 Python에서 분리 (현재/전일)
    rate_by_currency: dict[str, list] = {}
    for row in all_rate_rows:
        tc = row[0]
        if tc not in rate_by_currency:
            rate_by_currency[tc] = []
        if len(rate_by_currency[tc]) < 2:
            rate_by_currency[tc].append(row)

    for tc, rows in rate_by_currency.items():
        if not rows:
            continue
        current_rate = rows[0][1]
        change_pct = None
        if len(rows) >= 2:
            prev_rate = rows[1][1]
            if prev_rate and prev_rate > 0:
                change_pct = round(((current_rate - prev_rate) / prev_rate) * 100, 2)
        exchange_rates.append({
            "target_currency": tc,
            "rate": current_rate,
            "change_pct": change_pct,
        })

    if not commodities and not indices and not exchange_rates:
        return None

    # last_updated_at: 원자재/지수 중 가장 최근 날짜
    latest_dates: list[str] = []
    _cp_date_q = await db.execute(
        select(func.max(CommodityPrice.price_date))
        .where(CommodityPrice.symbol.in_(_commodity_symbols))
    )
    cp_max = _cp_date_q.scalar()
    if cp_max:
        latest_dates.append(str(cp_max))
    _mi_date_q = await db.execute(
        select(func.max(MarketIndex.index_date))
        .where(MarketIndex.symbol.in_(list(_HOME_INDEX_MAP.values())))
    )
    mi_max = _mi_date_q.scalar()
    if mi_max:
        latest_dates.append(str(mi_max))

    last_updated = max(latest_dates) if latest_dates else None

    return {
        "commodities": commodities,
        "indices": indices,
        "exchange_rates": exchange_rates,
        "last_updated_at": last_updated,
    }


async def _get_trade_exposure(
    home_country: str,
    db: AsyncSession,
) -> dict | None:
    """교역 노출도: 상위 5개 교역국 + 의존도%"""
    from backend.app.models.economic_data import TradeBilateral

    # 상위 교역 파트너 (최신 연도) — export/import 포함
    q = await db.execute(
        select(
            TradeBilateral.partner_code,
            TradeBilateral.total_trade_usd,
            TradeBilateral.export_value_usd,
            TradeBilateral.import_value_usd,
        )
        .where(
            TradeBilateral.reporter_code == home_country,
            TradeBilateral.period_type == "A",
        )
        .order_by(TradeBilateral.period.desc(), TradeBilateral.total_trade_usd.desc())
    )
    rows = q.all()

    # Fallback: 직접 보고 데이터 없으면 역방향 조회 (mirror trade)
    # 다른 나라가 이 나라를 파트너로 보고한 데이터 활용 (TW, KP 등 UN 비가맹국)
    is_mirror = False
    if not rows:
        q2 = await db.execute(
            select(
                TradeBilateral.reporter_code,    # 상대국이 "파트너" 역할
                TradeBilateral.total_trade_usd,
                TradeBilateral.import_value_usd,  # 상대국의 수입 = 우리 수출
                TradeBilateral.export_value_usd,  # 상대국의 수출 = 우리 수입
            )
            .where(
                TradeBilateral.partner_code == home_country,
                TradeBilateral.period_type == "A",
            )
            .order_by(TradeBilateral.period.desc(), TradeBilateral.total_trade_usd.desc())
        )
        rows = q2.all()
        is_mirror = True

    if not rows:
        return None

    seen = set()
    partners = []
    for partner_code, trade_usd, exp_usd, imp_usd in rows:
        if partner_code in seen or trade_usd is None:
            continue
        seen.add(partner_code)
        partners.append((partner_code, trade_usd, exp_usd, imp_usd))
        if len(partners) >= 5:
            break

    total_trade = sum(t for _, t, _, _ in partners)
    if total_trade <= 0:
        return None

    top_partners = []
    for pc, tv, exp_v, imp_v in partners:
        dep = round((tv / total_trade) * 100, 1)
        balance = None
        if exp_v is not None and imp_v is not None:
            balance = "surplus" if exp_v >= imp_v else "deficit"
        top_partners.append({
            "country_code": pc,
            "trade_volume_usd": tv,
            "dependency_pct": dep,
            "export_usd": exp_v,
            "import_usd": imp_v,
            "trade_balance": balance,
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


class _TradeDetail:
    """양자간 교역 상세 정보"""
    __slots__ = ("dependency", "total_usd", "export_usd", "import_usd")
    def __init__(self, dep: float, total: float, exp: float | None, imp: float | None):
        self.dependency = dep
        self.total_usd = total
        self.export_usd = exp
        self.import_usd = imp


async def _get_real_trade_detail(
    home_country: str,
    affected_country: str,
    db: AsyncSession,
) -> _TradeDetail | None:
    """DB에서 실제 양자간 교역 상세 조회 (의존도 + 교역액)"""
    from backend.app.models.economic_data import TradeBilateral

    pair_q = await db.execute(
        select(
            TradeBilateral.total_trade_usd,
            TradeBilateral.export_value_usd,
            TradeBilateral.import_value_usd,
        )
        .where(
            TradeBilateral.reporter_code == home_country,
            TradeBilateral.partner_code == affected_country,
            TradeBilateral.period_type == "A",
        )
        .order_by(TradeBilateral.period.desc())
        .limit(1)
    )
    row = pair_q.first()
    if row is None or row[0] is None:
        return None

    pair_trade, export_val, import_val = row[0], row[1], row[2]

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

    dep = min(1.0, pair_trade / total_trade)
    return _TradeDetail(round(dep, 3), pair_trade, export_val, import_val)


async def _get_real_trade_dependency(
    home_country: str,
    affected_country: str,
    db: AsyncSession,
) -> float | None:
    """하위호환 래퍼 — 의존도만 반환"""
    detail = await _get_real_trade_detail(home_country, affected_country, db)
    return detail.dependency if detail else None


# ── 토픽×섹터 영향 서술 사전 ──────────────────────────────────────────────
# (topic, sector) → {lang: {risk_level: description}}
_SECTOR_NARRATIVES: dict[tuple[str, str], dict[str, dict[str, str]]] = {
    # conflict
    ("conflict", "energy"): {
        "ko": {"critical": "원유·가스 공급 즉시 차질. 유가 급등 압력, 정유·항공·물류 마진 급락",
               "high": "주요 유전지역 불안정, 유가 5-10% 변동성 확대, 난방·수송 비용 상승",
               "medium": "공급 차질 제한적이나 유가 변동성 확대 모니터링 필요"},
        "en": {"critical": "Oil/gas supply disruption imminent. Fuel price spike, refinery & aviation margin collapse",
               "high": "Instability in key oil regions, 5-10% price volatility, heating & transport cost rise",
               "medium": "Limited supply impact but elevated price volatility warrants monitoring"},
    },
    ("conflict", "shipping"): {
        "ko": {"critical": "주요 해운 경로 차단 위험, 우회 비용 30-50% 증가, 납기 1-3주 지연",
               "high": "해운 보험료 급등 + 항로 우회, 물류 비용 15-25% 상승",
               "medium": "해상 운송 리스크 상승, 보험료 인상, 일부 선적 지연"},
        "en": {"critical": "Major shipping route blockage risk; rerouting costs +30-50%, 1-3 week delays",
               "high": "Shipping insurance surge + route diversion, logistics costs +15-25%",
               "medium": "Elevated maritime risk; insurance hikes, selective shipment delays"},
    },
    ("conflict", "semiconductor"): {
        "ko": {"critical": "희토류·특수가스 공급 중단, 칩 생산 차질, 납기 4-6주 지연",
               "high": "반도체 원자재 공급 불안, 납기 2-3주 지연, 재고 확보 경쟁 심화",
               "medium": "간접 영향. 글로벌 공급망 불확실성으로 선제 재고 확보 움직임"},
        "en": {"critical": "Rare earth / specialty gas supply cut, chip production halt, 4-6 week delays",
               "high": "Semiconductor raw material instability; 2-3 week delays, inventory competition",
               "medium": "Indirect impact. Precautionary stockpiling amid global uncertainty"},
    },
    ("conflict", "agriculture"): {
        "ko": {"critical": "곡물 수출국 분쟁, 밀·옥수수 공급 차단, 식품 가격 급등",
               "high": "식량 공급망 불안, 곡물 가격 10-20% 상승 압력, 사료 비용 연동",
               "medium": "식량 수급 모니터링 필요, 가격 변동 확대"},
        "en": {"critical": "Grain exporter conflict; wheat/corn supply blocked, food price surge",
               "high": "Food supply chain stress; grain prices +10-20%, feed cost spillover",
               "medium": "Food supply monitoring needed; price volatility widening"},
    },
    ("conflict", "defense"): {
        "ko": {"critical": "방산 수요 폭증, 군수품 납기 장기화, 방산주 급등",
               "high": "군비 확장 압력, 방산 부품 수급 긴장, 수출 기회 확대",
               "medium": "지정학 리스크 반영, 방위 예산 증액 논의 활발"},
        "en": {"critical": "Defense demand surge; military supply backlogs, defense stocks spike",
               "high": "Arms buildup pressure; defense parts supply tension, export opportunity",
               "medium": "Geopolitical risk priced in; defense budget increase discussions active"},
    },
    ("conflict", "tourism"): {
        "ko": {"critical": "분쟁 지역 전면 여행 금지. 항공편 취소, 인접국 관광 수요 급감",
               "high": "여행 경보 상향. 해당 지역 예약 취소 급증, 항공사 노선 조정",
               "medium": "여행 심리 위축. 인접 지역 관광 수요 소폭 감소"},
        "en": {"critical": "Full travel ban to conflict zone. Flight cancellations, adjacent tourism collapse",
               "high": "Travel advisory upgrade. Mass cancellations, airline route adjustments",
               "medium": "Travel sentiment weakened. Slight decline in adjacent tourism demand"},
    },
    # sanctions
    ("sanctions", "energy"): {
        "ko": {"critical": "에너지 수출 제재. 대체 조달처 확보 시급, 유가 $20+ 프리미엄",
               "high": "에너지 제재 확대, 우회 수입 비용 증가, 장기 계약 재협상 필요"},
        "en": {"critical": "Energy export sanctions. Urgent alternative sourcing, $20+ oil premium",
               "high": "Expanded energy sanctions; circumvention costs rise, contract renegotiation needed"},
    },
    ("sanctions", "manufacturing"): {
        "ko": {"critical": "제재 대상국 부품 즉시 수입 금지, 생산 라인 2-4주 중단 위험",
               "high": "제재 강화 시 부품 공급처 전환 필요, 전환 비용 10-15% 증가"},
        "en": {"critical": "Sanctioned parts import ban; production line shutdown risk for 2-4 weeks",
               "high": "Sanctions escalation requires supplier switch; transition cost +10-15%"},
    },
    ("sanctions", "semiconductor"): {
        "ko": {"critical": "칩 수출 통제, 고성능 반도체 공급 차단, 국내 제조 역량 의존 불가피",
               "high": "기술 제재 확대, EDA 도구·장비 접근 제한, 차세대 공정 개발 지연"},
        "en": {"critical": "Chip export controls; high-end semiconductor supply cut, domestic reliance forced",
               "high": "Tech sanctions widening; EDA tool/equipment access restricted, next-gen process delays"},
    },
    # cyber
    ("cyber", "technology"): {
        "ko": {"critical": "대규모 사이버 공격, 클라우드·금융 인프라 일시 마비, 기업 데이터 유출 위험",
               "high": "사이버 위협 고조, 보안 비용 급증, IT 서비스 일시 중단 가능"},
        "en": {"critical": "Major cyberattack; cloud/financial infrastructure outage, corporate data breach risk",
               "high": "Elevated cyber threat; security costs surge, IT service disruptions possible"},
    },
    ("cyber", "semiconductor"): {
        "ko": {"critical": "반도체 설계 IP 탈취 위험, 핵심 기술 유출, 수출 통제 강화 불가피",
               "high": "사이버 스파이 활동 증가, 설계 데이터 보호 강화 필요"},
        "en": {"critical": "Chip design IP theft risk; core tech leakage, export controls inevitable",
               "high": "Cyber espionage activity increase; design data protection reinforcement needed"},
    },
    # terror
    ("terror", "tourism"): {
        "ko": {"critical": "테러 발생. 해당국 여행 전면 금지, 글로벌 관광 심리 급랭",
               "high": "테러 위협 고조, 여행 보험료 인상, 예약 취소율 30% 이상"},
        "en": {"critical": "Terror attack. Full travel ban, global tourism sentiment collapses",
               "high": "Elevated terror threat; travel insurance hikes, cancellation rate >30%"},
    },
    ("terror", "energy"): {
        "ko": {"critical": "에너지 시설 테러, 정유·파이프라인 가동 중단, 유가 즉시 급등",
               "high": "에너지 인프라 위협, 시설 보안 강화 비용 증가, 보험료 인상"},
        "en": {"critical": "Energy facility attack; refinery/pipeline shutdown, immediate oil price spike",
               "high": "Energy infrastructure threat; facility security costs rise, insurance hikes"},
    },
}

# 위험도별 요약 / 공급차질 / 비용증가 / 시나리오 템플릿
_RISK_SUMMARY: dict[str, dict[str, str]] = {
    "ko": {"critical": "공급 차질 즉시 우려", "high": "2-4주 내 영향 가능", "medium": "모니터링 필요", "low": "직접 영향 낮음"},
    "en": {"critical": "Immediate supply disruption risk", "high": "Impact likely within 2-4 weeks", "medium": "Monitoring required", "low": "Low direct impact"},
}

_SUPPLY_DISRUPTION: dict[str, str] = {
    "critical": "2-6", "high": "1-3", "medium": "0-1", "low": "",
}

_COST_INCREASE: dict[str, str] = {
    "critical": "+20-40%", "high": "+10-20%", "medium": "+5-10%", "low": "",
}

_SCENARIO_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "worst": {"prefix": "악화 시: ", "suffix": ". 대체 조달 4주+, 생산 차질 불가피"},
        "base": {"prefix": "현 수준 유지 시: ", "suffix": ". 비용 부담 증가하나 관리 가능"},
        "best": {"prefix": "급속 완화 시: ", "suffix": ". 72시간 내 정상화, 일시적 변동만"},
    },
    "en": {
        "worst": {"prefix": "If worsened: ", "suffix": ". Alternative sourcing 4+ weeks, production disruption inevitable"},
        "base": {"prefix": "If status quo: ", "suffix": ". Cost pressure up but manageable"},
        "best": {"prefix": "If rapid resolution: ", "suffix": ". Normalization within 72h, temporary volatility only"},
    },
}


def _fmt_usd(val: float | None) -> str:
    """USD millions → 읽기 좋은 형식"""
    if val is None:
        return "?"
    if val >= 1000:
        return f"${val / 1000:.1f}B"
    return f"${val:.0f}M"


async def _calc_sector_exposure(
    home_country: str,
    affected_country: str,
    severity: int,
    lang: str = "ko",
    db: AsyncSession | None = None,
    topic: str = "",
    commodity_prices: dict | None = None,
) -> list[dict]:
    """섹터 노출도 계산 v2 — 토픽별 설명 + 교역액 + 시나리오 + 원자재"""
    sectors_data = SECTOR_DATA.get(home_country, DEFAULT_SECTORS)
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    l = "ko" if lang == "ko" else "en"

    # 섹터 GDP 비중 합계 (교역금액 비례배분용)
    total_gdp_pct = sum(info["gdp_pct"] for info in sectors_data.values()) or 1.0

    # DB 교역 상세 조회
    trade_detail: _TradeDetail | None = None
    if db:
        try:
            trade_detail = await _get_real_trade_detail(home_country, affected_country, db)
        except Exception:
            pass

    real_trade_dep = trade_detail.dependency if trade_detail else None

    result = []

    for sector, info in sectors_data.items():
        partners = info.get("key_partners", [])
        gdp_pct = info["gdp_pct"]
        sector_share = gdp_pct / total_gdp_pct  # 섹터 GDP 비중 (교역금액 비례배분용)

        is_partner = affected_country in partners
        partner_rank = partners.index(affected_country) + 1 if is_partner else 0

        if real_trade_dep is not None and real_trade_dep > 0.001:
            trade_dep = min(0.95, real_trade_dep * 3)
        elif is_partner:
            rank_map = {1: 0.85, 2: 0.6, 3: 0.35, 4: 0.25, 5: 0.18}
            trade_dep = rank_map.get(partner_rank, 0.12)
        else:
            _SECTOR_INDIRECT_WEIGHT: dict[str, float] = {
                "energy": 0.45, "shipping": 0.35, "agriculture": 0.25,
                "manufacturing": 0.20, "defense": 0.30, "semiconductor": 0.12,
                "electronics": 0.10, "automotive": 0.10, "technology": 0.12,
                "tourism": 0.15,
            }
            weight = _SECTOR_INDIRECT_WEIGHT.get(sector, 0.15)
            trade_dep = min(0.25, severity / 100 * weight)

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

        # 섹터별 교역금액 추정 (국가 전체 교역액 × 섹터 GDP 비중)
        sector_trade_usd = (trade_detail.total_usd or 0) * sector_share if trade_detail and trade_detail.total_usd else 0
        sector_export_usd = (trade_detail.export_usd or 0) * sector_share if trade_detail and trade_detail.export_usd else 0
        sector_import_usd = (trade_detail.import_usd or 0) * sector_share if trade_detail and trade_detail.import_usd else 0

        # ── 설명 생성 (v2: 토픽×섹터 사전 우선) ──
        narrative = _SECTOR_NARRATIVES.get((topic, sector), {}).get(l, {})
        desc_from_narrative = narrative.get(risk_level) or narrative.get("high") or narrative.get("medium")

        if desc_from_narrative:
            # 토픽별 구체 설명 + 교역 수치 보강
            desc = desc_from_narrative
            if sector_trade_usd > 0:
                vol = _fmt_usd(sector_trade_usd)
                pct = f"{real_trade_dep * 100:.1f}%" if real_trade_dep else ""
                if l == "ko":
                    desc += f" (교역 {vol}, 비중 {pct})" if pct else f" (교역 {vol})"
                else:
                    desc += f" (trade {vol}, share {pct})" if pct else f" (trade {vol})"
            elif is_partner:
                if l == "ko":
                    desc += f" ({sector_label} {partner_rank}위 파트너)"
                else:
                    desc += f" (#{partner_rank} {sector_label} partner)"
        else:
            # 폴백: 기존 템플릿 + 교역액 추가
            if l == "ko":
                desc = f"GDP 대비 {gdp_pct}% 비중. "
                if sector_trade_usd > 0:
                    desc += f"해당 지역과 교역 {_fmt_usd(sector_trade_usd)} (비중 {real_trade_dep * 100:.1f}%)."
                elif is_partner:
                    desc += f"해당 지역은 {sector_label} 분야 {partner_rank}위 교역 파트너."
                else:
                    desc += "직접 교역 관계는 낮으나 글로벌 공급망 간접 영향 가능."
            else:
                desc = f"{gdp_pct}% of GDP. "
                if sector_trade_usd > 0:
                    desc += f"Trade with affected region: {_fmt_usd(sector_trade_usd)} (share {real_trade_dep * 100:.1f}%)."
                elif is_partner:
                    desc += f"Affected region is #{partner_rank} trade partner for {sector_label}."
                else:
                    desc += "Low direct trade but potential indirect impact via global supply chains."

        # ── 원자재 가격 보강 (섹터별 관련 원자재) ──
        _SECTOR_COMMODITY_SYMS: dict[str, list[str]] = {
            "energy": ["WTI", "NATGAS"], "agriculture": ["WHEAT", "CORN"],
            "shipping": ["BDRY"], "mining": ["GOLD"], "tourism": ["JET_FUEL"],
        }
        _cp = commodity_prices or {}
        _sc_syms = _SECTOR_COMMODITY_SYMS.get(sector, [])
        for _sc_sym in _sc_syms:
            if _sc_sym in _cp:
                _sc_p, _sc_c = _cp[_sc_sym]
                _sc_ps = f"${_sc_p:,.0f}" if _sc_p >= 10 else f"${_sc_p:.2f}"
                _sc_sign = "+" if _sc_c > 0 else ""
                if l == "ko":
                    desc += f" {_sc_sym} {_sc_ps}({_sc_sign}{_sc_c:.1f}%)."
                else:
                    desc += f" {_sc_sym} {_sc_ps} ({_sc_sign}{_sc_c:.1f}%)."
                break  # 첫 매칭만

        # ── 시나리오 + action (Pro+ 이슈 상세용) ──
        s_tpl = _SCENARIO_TEMPLATES.get(l, _SCENARIO_TEMPLATES["en"])
        scenario_worst = scenario_base = scenario_best = action_point = None
        if risk_level in ("critical", "high"):
            scenario_worst = s_tpl["worst"]["prefix"] + desc.split("—")[0].strip() if "—" in desc else s_tpl["worst"]["prefix"] + sector_label
            scenario_worst += s_tpl["worst"]["suffix"]
            scenario_base = s_tpl["base"]["prefix"] + sector_label + s_tpl["base"]["suffix"]
            scenario_best = s_tpl["best"]["prefix"] + sector_label + s_tpl["best"]["suffix"]
            if l == "ko":
                action_point = f"대체 조달처 확보 및 재고 점검 필요" if trade_dep > 0.3 else f"공급망 모니터링 강화 권장"
            else:
                action_point = "Secure alternative sourcing and review inventory" if trade_dep > 0.3 else "Strengthen supply chain monitoring"

        entry: dict = {
            "sector": sector_label,
            "exposure_pct": gdp_pct,
            "trade_dependency": round(trade_dep, 2),
            "risk_level": risk_level,
            "description": desc,
            "risk_summary": _RISK_SUMMARY.get(l, _RISK_SUMMARY["en"]).get(risk_level, ""),
            "affected_countries": [affected_country] if (is_partner or (real_trade_dep and real_trade_dep > 0.001)) else [],
            "supply_disruption_weeks": _SUPPLY_DISRUPTION.get(risk_level) or None,
            "cost_increase_pct": _COST_INCREASE.get(risk_level) or None,
            "scenario_worst": scenario_worst,
            "scenario_base": scenario_base,
            "scenario_best": scenario_best,
            "action_point": action_point,
        }

        if sector_trade_usd > 0:
            entry["trade_volume_usd"] = round(sector_trade_usd, 1)
            entry["export_usd"] = round(sector_export_usd, 1) if sector_export_usd else None
            entry["import_usd"] = round(sector_import_usd, 1) if sector_import_usd else None

        result.append(entry)

    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    result.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
    return result


@router.get("/sector/{cluster_id}", response_model=SectorAnalysisOut)
async def get_sector_analysis(
    cluster_id: str,
    user: User = Depends(plan_required("pro_plus")),
    db: AsyncSession = Depends(get_db),
    lang: str | None = Query(None, description="응답 언어 (ko/en). 미지정 시 사용자 설정 사용"),
    home_country: str | None = Query(None, description="분석 기준 국가 (ISO2). 미지정 시 사용자 설정 사용"),
):
    """섹터별 영향도 분석 (Pro+ 이상)"""
    # 사용자 언어 결정 (쿼리 파라미터 > DB 설정 > 기본값)
    resolved_lang = lang
    if not resolved_lang:
        from backend.app.models.user import UserPreference
        pref_q = await db.execute(
            select(UserPreference.language).where(UserPreference.user_id == user.id)
        )
        pref_lang = pref_q.scalar_one_or_none()
        resolved_lang = pref_lang or "ko"
    lang = resolved_lang

    # 기준 국가 결정 (쿼리 파라미터 > 사용자 설정 > 기본값)
    redis = get_redis()
    home = home_country or user.home_country or "KR"
    cache_key = f"impact:sector:{_CACHE_VERSION}:{cluster_id}:{home}:{lang}"

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

    # 원자재 가격 조회 (섹터 설명 보강용)
    from backend.app.models.economic_data import CommodityPrice
    _sector_cp_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(["WTI", "NATGAS", "WHEAT", "CORN", "GOLD", "BDRY", "JET_FUEL"]))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )
    _sector_cp: dict[str, tuple[float, float]] = {}
    for _scp in _sector_cp_q.scalars():
        if _scp.symbol not in _sector_cp:
            _sector_cp[_scp.symbol] = (_scp.price_usd, _scp.change_pct or 0)
    sectors = await _calc_sector_exposure(home, affected, cluster.severity or 0, lang, db, topic=cluster.topic or "", commodity_prices=_sector_cp)
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


@router.get("/sector-overview", response_model=SectorAnalysisOut)
async def get_sector_overview(
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
    lang: str | None = Query(None, description="응답 언어 (ko/en)"),
    home_country: str | None = Query(None, description="분석 기준 국가 (ISO2)"),
):
    """전체 활성 이슈 기반 종합 섹터 리스크 분석 (모든 플랜)"""
    resolved_lang = lang
    if not resolved_lang:
        from backend.app.models.user import UserPreference
        pref_q = await db.execute(
            select(UserPreference.language).where(UserPreference.user_id == user.id)
        )
        pref_lang = pref_q.scalar_one_or_none()
        resolved_lang = pref_lang or "ko"
    lang = resolved_lang

    home = home_country or user.home_country or "KR"

    redis = get_redis()
    cache_key = f"impact:sector-overview:{_CACHE_VERSION}:{home}:{lang}"
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return SectorAnalysisOut(**data)

    # 최근 7일 활성 클러스터
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
        .limit(50)
    )
    clusters = clusters_q.scalars().all()

    if not clusters:
        return SectorAnalysisOut(
            home_country=home, affected_country="global",
            sectors=[], overall_risk="low",
            generated_at=datetime.now(timezone.utc).isoformat(), cached=False,
        )

    # 모든 클러스터의 국가별 최고 severity 집계
    country_severity: dict[str, int] = {}
    for c in clusters:
        cc = c.country_code or ""
        if not cc:
            continue
        sev = c.severity or 0
        if cc not in country_severity or sev > country_severity[cc]:
            country_severity[cc] = sev

    # 섹터별 노출도 집계: 실제 DB 교역 데이터 우선, 없으면 토픽 기반 간접 영향
    sectors_data = SECTOR_DATA.get(home, DEFAULT_SECTORS)
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    aggregated: dict[str, dict] = {}

    # 원자재 가격 조회 (섹터 설명 보강용)
    from backend.app.models.economic_data import CommodityPrice
    _ov_cp_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(["WTI", "NATGAS", "WHEAT", "CORN", "GOLD", "BDRY", "JET_FUEL"]))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )
    _overview_cp: dict[str, tuple[float, float]] = {}
    for _ovcp in _ov_cp_q.scalars():
        if _ovcp.symbol not in _overview_cp:
            _overview_cp[_ovcp.symbol] = (_ovcp.price_usd, _ovcp.change_pct or 0)

    # 섹터 GDP 비중 합계 (교역금액 비례배분용)
    total_gdp_pct = sum(info["gdp_pct"] for info in sectors_data.values()) or 1.0

    # 실제 교역 데이터 조회 (한 번만) — 모든 분쟁국 대상
    real_trade_details: dict[str, _TradeDetail | None] = {}
    for cc in country_severity:
        try:
            real_trade_details[cc] = await _get_real_trade_detail(home, cc, db)
        except Exception:
            real_trade_details[cc] = None

    # 토픽 → 관련 섹터 매핑 (간접 영향 계산용)
    _topic_sector_map: dict[str, list[str]] = {
        "conflict": ["energy", "shipping"],
        "terror": ["energy", "shipping", "tourism"],
        "military": ["energy", "shipping", "defense"],
        "economy": ["energy", "manufacturing", "shipping"],
        "trade": ["shipping", "manufacturing", "semiconductor"],
        "cyber": ["technology", "semiconductor", "electronics"],
        "diplomacy": ["energy", "shipping"],
        "sanctions": ["energy", "shipping", "manufacturing"],
        "humanitarian": ["agriculture"],
        "nuclear": ["energy", "defense"],
    }

    # 분쟁 클러스터의 토픽별 최고 severity 수집 (간접 영향용)
    topic_severity: dict[str, int] = {}
    # 국가별 지배적 토픽 추적 (설명 생성용)
    country_topic: dict[str, str] = {}
    for c in clusters:
        tp = c.topic or ""
        sev = c.severity or 0
        cc = c.country_code or ""
        if tp and (tp not in topic_severity or sev > topic_severity[tp]):
            topic_severity[tp] = sev
        if cc and tp:
            if cc not in country_topic:
                country_topic[cc] = tp

    # 전체 클러스터에서 가장 지배적인 토픽 (가장 높은 severity)
    dominant_topic = max(topic_severity, key=topic_severity.get, default="") if topic_severity else ""

    l = "ko" if lang == "ko" else "en"

    for sector, info in sectors_data.items():
        partners = info.get("key_partners", [])
        gdp_pct = info["gdp_pct"]
        sector_label = labels.get(sector, sector)

        max_trade_dep = 0.0
        max_risk_score = 0.0
        affected_countries: list[str] = []
        best_detail: _TradeDetail | None = None
        best_topic_for_sector = ""
        total_trade_usd = 0.0
        total_export_usd = 0.0
        total_import_usd = 0.0

        # 1차: 모든 분쟁국에 대해 실제 교역 데이터 + key_partners 체크
        for cc, sev in country_severity.items():
            detail = real_trade_details.get(cc)
            real_dep = detail.dependency if detail else None
            is_partner = cc in partners
            partner_rank = partners.index(cc) + 1 if is_partner else 0

            if real_dep is not None and real_dep > 0.001:
                trade_dep = min(0.95, real_dep * 3)
                affected_countries.append(cc)
                if detail:
                    # 섹터 GDP 비중으로 비례배분 (국가 전체 교역액 × 섹터 비중)
                    sector_share = gdp_pct / total_gdp_pct
                    total_trade_usd += (detail.total_usd or 0) * sector_share
                    total_export_usd += (detail.export_usd or 0) * sector_share
                    total_import_usd += (detail.import_usd or 0) * sector_share
                if best_detail is None or (real_dep > (best_detail.dependency or 0)):
                    best_detail = detail
                    best_topic_for_sector = country_topic.get(cc, dominant_topic)
            elif is_partner:
                if partner_rank == 1:
                    trade_dep = 0.85
                elif partner_rank == 2:
                    trade_dep = 0.6
                elif partner_rank <= 3:
                    trade_dep = 0.4
                else:
                    trade_dep = 0.2
                affected_countries.append(cc)
                if not best_topic_for_sector:
                    best_topic_for_sector = country_topic.get(cc, dominant_topic)
            else:
                continue

            risk_score = trade_dep * (sev / 100)
            if trade_dep > max_trade_dep:
                max_trade_dep = trade_dep
            if risk_score > max_risk_score:
                max_risk_score = risk_score

        # 2차: 직접 교역 매칭이 없으면 토픽 기반 간접 영향 반영
        _SECTOR_INDIRECT_W: dict[str, float] = {
            "energy": 0.45, "shipping": 0.35, "agriculture": 0.25,
            "manufacturing": 0.20, "defense": 0.30, "semiconductor": 0.12,
            "electronics": 0.10, "automotive": 0.10, "technology": 0.12,
            "tourism": 0.15,
        }
        if not affected_countries:
            for tp, related_sectors in _topic_sector_map.items():
                if sector in related_sectors and tp in topic_severity:
                    sev = topic_severity[tp]
                    base_w = _SECTOR_INDIRECT_W.get(sector, 0.15)
                    indirect_dep = base_w * (sev / 100)
                    indirect_dep = min(0.25, indirect_dep)
                    risk_score = indirect_dep * (sev / 100)
                    if indirect_dep > max_trade_dep:
                        max_trade_dep = indirect_dep
                    if risk_score > max_risk_score:
                        max_risk_score = risk_score
                    if not best_topic_for_sector:
                        best_topic_for_sector = tp

        if max_risk_score >= 0.6:
            risk_level = "critical"
        elif max_risk_score >= 0.4:
            risk_level = "high"
        elif max_risk_score >= 0.2:
            risk_level = "medium"
        else:
            risk_level = "low"

        # ── 설명 생성 v2: 토픽×섹터 사전 우선 ──
        n_affected = len(affected_countries)
        narrative = _SECTOR_NARRATIVES.get((best_topic_for_sector, sector), {}).get(l, {})
        desc_from_narrative = narrative.get(risk_level) or narrative.get("high") or narrative.get("medium")

        if desc_from_narrative:
            desc = desc_from_narrative
            if total_trade_usd > 0:
                vol = _fmt_usd(total_trade_usd)
                if l == "ko":
                    desc += f" ({n_affected}개국 교역 {vol})" if n_affected > 1 else f" (교역 {vol})"
                else:
                    desc += f" ({n_affected} countries, trade {vol})" if n_affected > 1 else f" (trade {vol})"
            elif n_affected > 0:
                if l == "ko":
                    desc += f" ({n_affected}개 분쟁국 영향)"
                else:
                    desc += f" ({n_affected} conflict countries affected)"
        else:
            if l == "ko":
                desc = f"GDP 대비 {gdp_pct}% 비중. "
                if n_affected > 0 and total_trade_usd > 0:
                    dep_pct = best_detail.dependency * 100 if best_detail and best_detail.dependency else 0
                    desc += f"{n_affected}개 분쟁국과 교역 {_fmt_usd(total_trade_usd)}"
                    if dep_pct > 0:
                        desc += f" (비중 {dep_pct:.1f}%)"
                elif n_affected > 0:
                    desc += f"현재 {n_affected}개 분쟁국이 핵심 교역 파트너."
                elif max_trade_dep > 0:
                    desc += "글로벌 공급망 통한 간접 영향 가능."
                else:
                    desc += "현재 분쟁 지역과 직접 교역 노출 없음."
            else:
                desc = f"{gdp_pct}% of GDP. "
                if n_affected > 0 and total_trade_usd > 0:
                    dep_pct = best_detail.dependency * 100 if best_detail and best_detail.dependency else 0
                    desc += f"Trade with {n_affected} conflict zones: {_fmt_usd(total_trade_usd)}"
                    if dep_pct > 0:
                        desc += f" (share {dep_pct:.1f}%)"
                elif n_affected > 0:
                    desc += f"{n_affected} conflict-affected countries are key partners."
                elif max_trade_dep > 0:
                    desc += "Indirect exposure through global supply chains."
                else:
                    desc += "No direct trade exposure with conflict zones."

        # ── 원자재 가격 인라인 (sector-overview) ──
        _SECTOR_COMMODITY_SYMS_OV: dict[str, list[str]] = {
            "energy": ["WTI", "NATGAS"], "agriculture": ["WHEAT", "CORN"],
            "shipping": ["BDRY"], "mining": ["GOLD"], "tourism": ["JET_FUEL"],
        }
        for _ov_sym in _SECTOR_COMMODITY_SYMS_OV.get(sector, []):
            if _ov_sym in _overview_cp:
                _ov_p, _ov_c = _overview_cp[_ov_sym]
                _ov_ps = f"${_ov_p:,.0f}" if _ov_p >= 10 else f"${_ov_p:.2f}"
                _ov_sign = "+" if _ov_c > 0 else ""
                if l == "ko":
                    desc += f" {_ov_sym} {_ov_ps}({_ov_sign}{_ov_c:.1f}%)."
                else:
                    desc += f" {_ov_sym} {_ov_ps} ({_ov_sign}{_ov_c:.1f}%)."
                break

        entry: dict = {
            "sector": sector_label,
            "exposure_pct": gdp_pct,
            "trade_dependency": round(max_trade_dep, 2),
            "risk_level": risk_level,
            "description": desc,
            "risk_summary": _RISK_SUMMARY.get(l, _RISK_SUMMARY["en"]).get(risk_level, ""),
            "affected_countries": affected_countries[:5],
        }
        if total_trade_usd > 0:
            entry["trade_volume_usd"] = round(total_trade_usd, 1)
            entry["export_usd"] = round(total_export_usd, 1) if total_export_usd else None
            entry["import_usd"] = round(total_import_usd, 1) if total_import_usd else None

        aggregated[sector] = entry

    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sectors_list = sorted(aggregated.values(), key=lambda x: risk_order.get(x["risk_level"], 4))

    critical_count = sum(1 for s in sectors_list if s["risk_level"] == "critical")
    high_count = sum(1 for s in sectors_list if s["risk_level"] == "high")
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
        "affected_country": "global",
        "sectors": sectors_list,
        "overall_risk": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }

    if redis:
        await redis.set(cache_key, json.dumps(response_data), ex=6 * 3600)

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
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 행동 이벤트 기록 (미인증 시 무시)"""
    if not user:
        return {"ok": True}
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
    user: User = Depends(plan_required("pro")),
    db: AsyncSession = Depends(get_db),
):
    """국가간 교역 흐름 Sankey 데이터 (Pro 이상)

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
