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
_CACHE_VERSION = "v6"

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
    color: str
    category: str

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


@router.get("/summary", response_model=ImpactSummaryOut)
async def get_impact_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    home_country: str | None = Query(None, description="홈 국가 코드 (빈 문자열=글로벌)"),
    lang: str | None = Query(None, description="응답 언어 (ko/en). 미지정 시 사용자 설정 사용"),
):
    """홀리스틱 종합 영향도 (모든 플랜).

    사용자 홈 국가에 영향을 미치는 모든 활성 클러스터를 종합하여
    안정적인 영향도 점수와 요약을 반환합니다.
    - Free: score + summary + top_issues_count
    - Pro/Pro+: economy/trade/travel 상세 분석 포함
    """
    # 프론트엔드에서 home_country 파라미터를 보내면 우선 사용
    if home_country is not None:
        home = home_country  # 빈 문자열 = 글로벌 모드
    else:
        home = user.home_country or ""
    is_global = not home
    user_plan = user.plan or "free"

    # 사용자 언어 결정 (쿼리 파라미터 > DB 설정 > 기본값)
    resolved_lang = lang  # 쿼리 파라미터
    if not resolved_lang:
        from backend.app.models.user import UserPreference
        pref_q = await db.execute(
            select(UserPreference.language).where(UserPreference.user_id == user.id)
        )
        pref_lang = pref_q.scalar_one_or_none()
        resolved_lang = pref_lang or "ko"
    lang = resolved_lang

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

    # Top 5 이슈: personalizedKScore (kscore × impact_factor) 기준 정렬
    # (종합 점수는 impact score 기반, 이슈 목록은 KScore 기반 — 클라이언트와 동일)
    pkscore_sorted = sorted(
        scored,
        key=lambda x: -(
            (x[0].kscore or 0) * calc_impact_factor(
                x[0].country_code or "", x[0].topic or "unknown", home
            )
        ),
    )
    top5_for_issues = pkscore_sorted[:5]

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

    top_issues = []
    for c, impact in top5_for_issues:
        reason = _build_reason_sync(c, home, lang, sectors_data, trade_map, oil_row)
        smart = _build_smart_summary(c, home, lang, sectors_data, trade_map, oil_row)

        recent_count = recent_counts.get(c.id, 0)
        current_kscore = c.kscore or 0
        if recent_count > 0:
            kscore_delta = round(min(5.0, recent_count * 0.5), 1)
        else:
            kscore_delta = round(-min(1.0, current_kscore * 0.1), 1) if current_kscore > 1 else 0

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
            independent_sources=c.independent_sources or 0,
            is_spike=c.is_spike or False,
            confidence=round(c.confidence or 0.0, 3),
            first_event_at=c.first_event_at.isoformat() if c.first_event_at else None,
            last_event_at=c.last_event_at.isoformat() if c.last_event_at else None,
            entity_anchor=c.entity_anchor,
            body_snippet=body_snippets.get(c.id),
            what_line=smart["what_line"],
            so_what_line=smart["so_what_line"],
            when_line=smart["when_line"],
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

    is_pro = user_plan in ("pro", "pro_plus") or getattr(user, "admin_plan_override", False)

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
        home_idx_map = {"KR": "KOSPI", "US": "SPX", "JP": "NKY", "CN": "SSE", "DE": "DAX", "GB": "FTSE"}
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

        # 경제 지표 조회 (인플레이션, 교역비중, 경상수지)
        from backend.app.models.economic_data import EconomicIndicator
        econ_extras: dict[str, float | None] = {}
        if home:
            for ind_code, key in [
                ("FP.CPI.TOTL.ZG", "inflation"),
                ("NE.TRD.GNFS.ZS", "trade_openness"),
                ("BN.CAB.XOKA.CD", "current_account"),
            ]:
                eq = await db.execute(
                    select(EconomicIndicator.value)
                    .where(
                        EconomicIndicator.country_code == home,
                        EconomicIndicator.indicator_code == ind_code,
                    )
                    .order_by(EconomicIndicator.year.desc())
                    .limit(1)
                )
                econ_extras[key] = eq.scalar_one_or_none()

        if lang == "ko":
            display_home = "글로벌" if is_global else home
            # ── Economy: 구체적 수치 + 비자명적 분석 ──
            econ_parts = []
            if energy_risk and oil_row:
                price, chg = oil_row
                if chg > 0:
                    econ_parts.append(f"유가 ${price:,.0f}({chg:+.1f}%) — 배럴당 $80+ 지속 시 정유·항공·물류 마진 압박 예상")
                else:
                    econ_parts.append(f"유가 ${price:,.0f}({chg:+.1f}%) — 하락세지만 중동 리스크 프리미엄 상존")
            elif oil_str:
                econ_parts.append(f"유가 {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"금 ${gold_row[0]:,.0f}({gold_row[1]:+.1f}%) 안전자산 선호 확대 — 리스크오프 심리 강화 신호")
            elif gold_row and gold_row[1] < -1.0:
                econ_parts.append(f"금 ${gold_row[0]:,.0f}({gold_row[1]:+.1f}%) 하락 — 리스크 완화 또는 달러 강세 영향")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details:
                econ_parts.append(f"영향 섹터: {', '.join(sector_details[:3])} — 관련주 변동성 확대 구간")
            # 경제 지표 추가 인사이트
            inflation_val = econ_extras.get("inflation")
            trade_open_val = econ_extras.get("trade_openness")
            ca_val = econ_extras.get("current_account")
            if inflation_val and inflation_val > 5:
                econ_parts.append(f"인플레이션 {inflation_val:.1f}% — 원자재 상승 시 추가 물가 압력")
            if trade_open_val and trade_open_val > 80:
                econ_parts.append(f"교역/GDP {trade_open_val:.0f}% — 글로벌 공급망 교란에 높은 노출")
            if ca_val and ca_val < 0:
                econ_parts.append("경상수지 적자 — 외환 유출 리스크")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"{display_home} 경제 직접 영향 제한적, 간접 파급 모니터링 중."

            # ── Trade: 의존도 비율 + 공급망 시사점 ──
            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{display_home}↔{top_tv[0]} 교역 {_fmt_usd(top_tv[1])} — 분쟁국 중 최대 노출 지점")
                if len(sorted_tv) > 1:
                    for c, v in sorted_tv[1:3]:
                        trade_parts.append(f"{display_home}↔{c} {_fmt_usd(v)} 교역 분쟁 영향권 내")
                if energy_risk and total_conflict_trade > 0:
                    trade_parts.append(f"에너지 수입선 다변화 불가 시 공급 차질 리스크 — 대체 조달 소요 최소 2-4주")
            elif energy_risk:
                trade_parts.append("에너지 수입 의존국 불안정 — 유가·가스 가격 연동 리스크 확대")
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
                    travel_parts.append(f"이슈 관련 {len(lv4_in_issues)}개국 여행금지(Lv.4): {', '.join(lv4_in_issues[:4])} — 인접국 경유편 취소·감편 가능성")
                travel_parts.append(f"전 세계 {lv4_count}개국 여행금지 상태 — 분쟁 확산 시 인접국 경보 상향 가능")
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
                    econ_parts.append(f"Oil ${price:,.0f} ({chg:+.1f}%) — sustained above $80/bbl pressures refinery, airline & logistics margins")
                else:
                    econ_parts.append(f"Oil ${price:,.0f} ({chg:+.1f}%) — declining, but geopolitical risk premium persists")
            elif oil_str:
                econ_parts.append(f"Oil {oil_str}")
            if gold_row and gold_row[1] > 1.0:
                econ_parts.append(f"Gold ${gold_row[0]:,.0f} ({gold_row[1]:+.1f}%) rising — risk-off sentiment strengthening")
            elif gold_row and gold_row[1] < -1.0:
                econ_parts.append(f"Gold ${gold_row[0]:,.0f} ({gold_row[1]:+.1f}%) falling — risk easing or dollar strength")
            if idx_str:
                econ_parts.append(idx_str)
            if sector_details:
                econ_parts.append(f"Exposed sectors: {', '.join(sector_details[:3])} — elevated volatility expected")
            # Economic indicator insights
            inflation_val = econ_extras.get("inflation")
            trade_open_val = econ_extras.get("trade_openness")
            ca_val = econ_extras.get("current_account")
            if inflation_val and inflation_val > 5:
                econ_parts.append(f"Inflation {inflation_val:.1f}% — commodity spikes add further price pressure")
            if trade_open_val and trade_open_val > 80:
                econ_parts.append(f"Trade/GDP {trade_open_val:.0f}% — high exposure to global supply chain disruptions")
            if ca_val and ca_val < 0:
                econ_parts.append("Current account deficit — forex outflow risk")
            economy = ". ".join(econ_parts) + "." if econ_parts else f"{display_home} economy: limited direct impact, monitoring indirect spillover."

            trade_parts = []
            if trade_vols:
                sorted_tv = sorted(trade_vols.items(), key=lambda x: -x[1])
                top_tv = sorted_tv[0]
                trade_parts.append(f"{display_home}↔{top_tv[0]} trade at {_fmt_usd(top_tv[1])} — primary conflict exposure")
                if len(sorted_tv) > 1:
                    for c, v in sorted_tv[1:3]:
                        trade_parts.append(f"{display_home}↔{c} {_fmt_usd(v)} within conflict zone")
                if energy_risk and total_conflict_trade > 0:
                    trade_parts.append("Energy supply diversification lag 2-4 weeks if disrupted")
            elif energy_risk:
                trade_parts.append("Energy import dependency at risk — oil & gas price pass-through likely")
            if not trade_parts:
                trade_parts.append(f"Direct trade exposure for {display_home} limited; global supply chain spillover possible")
            trade = ". ".join(trade_parts) + "."

            travel_parts = []
            if lv4_count > 0:
                travel_parts.append(f"{lv4_count} countries at Do Not Travel (Lv.4) — adjacent transit routes may face cancellations")
            if critical_count > 0:
                travel_parts.append(f"{critical_count} high-impact issues — flight disruptions & insurance surcharges possible")
            if not travel_parts:
                travel_parts.append("No major travel restrictions. Monitoring advisory escalation near conflict zones")
            travel = ". ".join(travel_parts) + "."

    # ── 시장 동향 (market_snapshot) — 모든 플랜 ──
    market_snapshot = None
    try:
        market_snapshot = await _get_market_snapshot(home, db)
    except Exception as e:
        logger.warning("market_snapshot_error", error=str(e))

    # ── 교역 노출도 — Free: top 3 (dependency만), Pro: top 5 (full) ──
    trade_exposure = None
    try:
        # 글로벌 모드면 US 기준으로 fallback
        trade_home = home if home else "US"
        trade_exposure_data = await _get_trade_exposure(trade_home, db)
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
    except Exception as e:
        logger.warning("trade_exposure_error", error=str(e))

    # ── 여행 경보 (travel_advisories) — 모든 플랜 ──
    travel_advisories = []
    try:
        travel_advisories = await _get_travel_advisories(home, scored[:10], is_pro, db)
    except Exception as e:
        logger.warning("travel_advisories_error", error=str(e))

    # ── Risk Radar (모든 플랜) ──
    risk_radar = None
    try:
        risk_radar_obj = await _compute_risk_radar(home, scored, sectors_data, oil_row, db)
        risk_radar = risk_radar_obj.model_dump() if risk_radar_obj else None
    except Exception as e:
        logger.warning("risk_radar_error", error=str(e))

    # ── Impact Flow (모든 플랜) ──
    impact_flow = None
    try:
        impact_flow_obj = _compute_impact_flow(scored, home, sectors_data, trade_map, oil_row, lang)
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
    return f"impact:brief:{cluster_id}:{home_country}:{lang}"


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

    # AI 분석 생성
    brief = await _generate_impact_brief(cluster, effective_home, lang, db)

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
_HOME_CURRENCIES = {
    "KR": ["KRW", "JPY", "CNY", "EUR"],
    "US": ["EUR", "JPY", "GBP", "CNY"],
    "JP": ["JPY", "KRW", "CNY", "EUR"],
    "CN": ["CNY", "JPY", "KRW", "EUR"],
    "DE": ["EUR", "GBP", "JPY", "CNY"],
    "GB": ["GBP", "EUR", "JPY", "CNY"],
}


def _build_reason_sync(
    cluster,
    home_country: str,
    lang: str,
    sectors_data: dict,
    trade_map: dict[str, float],
    oil_row,
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

    oil_price = None
    if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY"):
        if oil_row:
            oil_price = (oil_row[0], oil_row[1])

    # 국가 코드 → 국가명 변환 (reason 가독성)
    h_name = _country_name(home_country, lang)
    c_name = _country_name(cc, lang)

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


def _build_smart_summary(cluster, home_country: str, lang: str, sectors_data: dict, trade_map: dict, oil_row) -> dict:
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

    # so_what_line
    oil_price = None
    if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY"):
        if oil_row:
            oil_price = (oil_row[0], oil_row[1])

    if lang == "ko":
        if oil_price:
            so_what_line = f"유가 ${oil_price[0]:,.0f}({oil_price[1]:+.1f}%), 가스비·물류비 상승 압력"
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name}과 교역 {trade_str}, {top_sector} 수입품 가격 상승 예상"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name} 관련 {top_sector}(GDP {gdp}%) 변동성 확대"
        else:
            so_what_line = _build_reason_sync(cluster, home_country, lang, sectors_data, trade_map, oil_row)
    else:
        if oil_price:
            so_what_line = f"Oil ${oil_price[0]:,.0f} ({oil_price[1]:+.1f}%), gas & logistics cost pressure"
        elif affected_sectors and trade_str:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"Trade with {c_name} {trade_str}, {top_sector} import prices may rise"
        elif affected_sectors:
            top_sector, gdp = affected_sectors[0]
            so_what_line = f"{c_name}-linked {top_sector} (GDP {gdp}%) — volatility expected"
        else:
            so_what_line = _build_reason_sync(cluster, home_country, lang, sectors_data, trade_map, oil_row)

    # when_line
    if lang == "ko":
        if severity >= 80 and topic in ("conflict", "terror"):
            when_line = "즉각적 — 시장 이미 반영 중"
        elif severity >= 60:
            when_line = "1-2주 내 공급망 영향"
        elif severity >= 40:
            when_line = "1-3개월 모니터링 필요"
        else:
            when_line = "간접 영향 — 추이 관찰"
    else:
        if severity >= 80 and topic in ("conflict", "terror"):
            when_line = "Immediate — markets pricing in"
        elif severity >= 60:
            when_line = "Supply chain impact in 1-2 weeks"
        elif severity >= 40:
            when_line = "Monitor over 1-3 months"
        else:
            when_line = "Indirect — monitoring trend"

    return {"what_line": what_line, "so_what_line": so_what_line, "when_line": when_line}


async def _compute_risk_radar(home: str, scored: list, sectors_data: dict, oil_row, db) -> RiskRadarOut | None:
    """Risk Radar 5축 계산"""
    if not scored:
        return None

    from backend.app.models.tension_index import TensionIndex
    from backend.app.models.economic_data import MarketIndex

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
    energy_score = min(100, energy_gdp * 3 + oil_change * 5 + energy_issues * 10)

    trade_issues = sum(1 for c, _ in scored[:20] if any(
        (c.country_code or "") in info.get("key_partners", [])
        for info in sectors_data.values()
    ))
    trade_score = min(100, trade_issues * 8 + len(scored[:20]) * 2)

    agri_data = sectors_data.get("agriculture", {})
    agri_gdp = agri_data.get("gdp_pct", 5.0)
    agri_partners = set(agri_data.get("key_partners", []))
    agri_issues = sum(1 for c, _ in scored[:20] if (c.country_code or "") in agri_partners)
    food_score = min(100, agri_gdp * 2 + agri_issues * 15)

    # Finance: market index change
    try:
        home_idx_map = {"KR": "KOSPI", "US": "SPX", "JP": "NKY", "CN": "SSE", "DE": "DAX", "GB": "FTSE"}
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


def _compute_impact_flow(scored: list, home: str, sectors_data: dict, trade_map: dict, oil_row, lang: str) -> ImpactFlowOut | None:
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

    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    nodes = []
    links = []
    seen_commodities = set()

    top3 = scored[:3]
    for idx, (c, impact) in enumerate(top3):
        cc = c.country_code or ""
        severity = c.severity or 0
        title = c.title_ko if lang == "ko" and c.title_ko else c.title or f"Issue {idx+1}"
        title = title[:20]
        node_id = f"c{idx}"
        nodes.append(ImpactFlowNode(id=node_id, label=title, color="#dc2626", category="conflict"))

        # Find affected commodities/sectors
        for sector, info in sectors_data.items():
            if cc in info.get("key_partners", []):
                commodity_id = sector
                if commodity_id not in seen_commodities:
                    seen_commodities.add(commodity_id)
                    nodes.append(ImpactFlowNode(
                        id=commodity_id, label=labels.get(sector, sector),
                        color="#f59e0b", category="commodity"
                    ))
                link_value = round(severity * info.get("gdp_pct", 1) / 100, 2)
                if link_value > 0:
                    links.append(ImpactFlowLink(source=node_id, target=commodity_id, value=max(1, link_value)))

    # Fallback: 매칭 실패 시 글로벌 합산 데이터로 재시도
    if not links and home:
        nodes = []
        links = []
        seen_commodities = set()
        fallback_sectors = _build_merged_sectors()
        for idx, (c, impact) in enumerate(top3):
            cc = c.country_code or ""
            severity = c.severity or 0
            title = c.title_ko if lang == "ko" and c.title_ko else c.title or f"Issue {idx+1}"
            title = title[:20]
            node_id = f"c{idx}"
            nodes.append(ImpactFlowNode(id=node_id, label=title, color="#dc2626", category="conflict"))
            for sector, info in fallback_sectors.items():
                if cc in info.get("key_partners", []):
                    commodity_id = sector
                    if commodity_id not in seen_commodities:
                        seen_commodities.add(commodity_id)
                        nodes.append(ImpactFlowNode(
                            id=commodity_id, label=labels.get(sector, sector),
                            color="#f59e0b", category="commodity"
                        ))
                    link_value = round(severity * info.get("gdp_pct", 1) / 100, 2)
                    if link_value > 0:
                        links.append(ImpactFlowLink(source=node_id, target=commodity_id, value=max(1, link_value)))

    # Right column: impact categories — 실제 데이터 기반 라벨
    oil_change = oil_row[1] if oil_row else 0
    oil_price = oil_row[0] if oil_row else 0
    h_name = _country_name(home, lang)
    impact_items = []
    if "energy" in seen_commodities:
        if oil_change != 0:
            lbl = f"에너지 비용 {oil_change:+.1f}%" if lang == "ko" else f"Energy costs {oil_change:+.1f}%"
        else:
            lbl = "에너지 비용 상승" if lang == "ko" else "Energy cost rise"
        impact_items.append(("energy_cost", lbl))
    if "agriculture" in seen_commodities:
        lbl = "식료품 가격 상승" if lang == "ko" else "Food prices up"
        impact_items.append(("food_cost", lbl))
    if "shipping" in seen_commodities:
        lbl = "물류비 상승" if lang == "ko" else "Shipping costs up"
        impact_items.append(("shipping_cost", lbl))
    if "semiconductor" in seen_commodities or "electronics" in seen_commodities or "technology" in seen_commodities:
        lbl = "전자제품 가격 상승" if lang == "ko" else "Electronics prices up"
        impact_items.append(("electronics_cost", lbl))
    if "automotive" in seen_commodities:
        lbl = "자동차 가격 영향" if lang == "ko" else "Auto prices affected"
        impact_items.append(("auto_cost", lbl))
    if "manufacturing" in seen_commodities:
        lbl = "제조 원가 상승" if lang == "ko" else "Mfg costs up"
        impact_items.append(("mfg_cost", lbl))
    if "tourism" in seen_commodities:
        lbl = "여행 경비 영향" if lang == "ko" else "Travel costs affected"
        impact_items.append(("travel_cost", lbl))

    if not impact_items:
        lbl = "물가 상승 압력" if lang == "ko" else "Inflation pressure"
        impact_items.append(("inflation", lbl))

    for imp_id, imp_label in impact_items:
        nodes.append(ImpactFlowNode(id=imp_id, label=imp_label, color="#3b82f6", category="impact"))
        # Link commodities to impacts
        for commodity_id in seen_commodities:
            links.append(ImpactFlowLink(source=commodity_id, target=imp_id, value=1))

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

    # 1) 원자재: 1 배치 쿼리 (DISTINCT ON)
    commodity_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(["WTI", "BRENT", "GOLD"]))
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
        .where(MarketIndex.symbol.in_(["KOSPI", "SPX", "NKY", "DAX", "FTSE", "SSE"]))
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

    # 3) 환율: 1 배치 쿼리 (최신만)
    target_currencies = _HOME_CURRENCIES.get(home_country, ["EUR", "JPY", "GBP", "CNY"])
    rate_q = await db.execute(
        select(ExchangeRate)
        .distinct(ExchangeRate.target_currency)
        .where(
            ExchangeRate.base_currency == "USD",
            ExchangeRate.target_currency.in_(target_currencies),
        )
        .order_by(ExchangeRate.target_currency, ExchangeRate.rate_date.desc())
    )
    latest_rates = rate_q.scalars().all()

    # 전일 대비를 위한 2번째 최신 배치 조회
    if latest_rates:
        # 각 통화의 최신 날짜를 모아서 이전 데이터 조회
        for row in latest_rates:
            prev_q = await db.execute(
                select(ExchangeRate.rate)
                .where(
                    ExchangeRate.base_currency == "USD",
                    ExchangeRate.target_currency == row.target_currency,
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
    cache_key = f"impact:sector:{cluster_id}:{home}:{lang}"

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


@router.get("/sector-overview", response_model=SectorAnalysisOut)
async def get_sector_overview(
    user: User = Depends(get_current_user),
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

    # 섹터별 노출도 집계: 모든 분쟁 국가에 대해 계산 후 최대값 취합
    sectors_data = SECTOR_DATA.get(home, DEFAULT_SECTORS)
    labels = SECTOR_LABELS.get(lang, SECTOR_LABELS["en"])
    aggregated: dict[str, dict] = {}

    # 실제 교역 데이터 조회 (한 번만)
    real_trade_deps: dict[str, float | None] = {}
    for cc in country_severity:
        try:
            real_trade_deps[cc] = await _get_real_trade_dependency(home, cc, db)
        except Exception:
            real_trade_deps[cc] = None

    for sector, info in sectors_data.items():
        partners = info.get("key_partners", [])
        gdp_pct = info["gdp_pct"]
        sector_label = labels.get(sector, sector)

        max_trade_dep = 0.05
        max_risk_score = 0.0
        affected_countries = []

        for cc, sev in country_severity.items():
            is_partner = cc in partners
            if not is_partner:
                continue
            partner_rank = partners.index(cc) + 1
            affected_countries.append(cc)

            real_dep = real_trade_deps.get(cc)
            if real_dep is not None:
                rank_weight = max(0.3, 1.0 - (partner_rank - 1) * 0.15)
                trade_dep = min(0.95, real_dep * rank_weight * 3)
            elif partner_rank == 1:
                trade_dep = 0.85
            elif partner_rank == 2:
                trade_dep = 0.6
            elif partner_rank <= 3:
                trade_dep = 0.4
            else:
                trade_dep = 0.2

            risk_score = trade_dep * (sev / 100)
            if trade_dep > max_trade_dep:
                max_trade_dep = trade_dep
            if risk_score > max_risk_score:
                max_risk_score = risk_score

        if max_risk_score >= 0.6:
            risk_level = "critical"
        elif max_risk_score >= 0.4:
            risk_level = "high"
        elif max_risk_score >= 0.2:
            risk_level = "medium"
        else:
            risk_level = "low"

        n_affected = len(affected_countries)
        if lang == "ko":
            desc = f"GDP 대비 {gdp_pct}% 비중. "
            if n_affected > 0:
                desc += f"현재 {n_affected}개 분쟁국이 핵심 교역 파트너."
            else:
                desc += "현재 분쟁국 중 핵심 교역 파트너 없음."
        else:
            desc = f"{gdp_pct}% of GDP. "
            if n_affected > 0:
                desc += f"{n_affected} conflict-affected countries are key partners."
            else:
                desc += "No key trade partners currently in conflict zones."

        aggregated[sector] = {
            "sector": sector_label,
            "exposure_pct": gdp_pct,
            "trade_dependency": round(max_trade_dep, 2),
            "risk_level": risk_level,
            "description": desc,
        }

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
