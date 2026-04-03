"""
v2.0 Consumer Translation Layer
- 원자재 → 생활 영향 번역
- Trust Level 4단계
- Sensor Context 자연어
- Weather 5단계
- Consumer 필드 (what/so_what/when/wallet)
"""

from __future__ import annotations

# ── 원자재 → 소비자 생활 영향 매핑 ──────────────────────────────────
COMMODITY_CONSUMER_MAP: dict[str, dict[str, str]] = {
    "WTI":     {"ko": "주유비·택배비에 영향이 올 수 있어요", "en": "Gas & shipping costs may be affected"},
    "BRENT":   {"ko": "주유비·택배비에 영향이 올 수 있어요", "en": "Gas & shipping costs may be affected"},
    "WHEAT":   {"ko": "빵·면 가격이 불안정해질 수 있어요", "en": "Bread & noodle prices may be affected"},
    "CORN":    {"ko": "축산물·사료 가격에 영향 가능", "en": "Livestock & feed prices may be affected"},
    "RICE":    {"ko": "쌀값에 영향이 올 수 있어요", "en": "Rice prices may be affected"},
    "SOYBEAN": {"ko": "식용유·두부 가격에 영향 가능", "en": "Cooking oil & tofu prices may be affected"},
    "NATGAS":  {"ko": "가스비·난방비에 영향이 올 수 있어요", "en": "Gas & heating costs may be affected"},
    "BDRY":    {"ko": "배달비·물류비 상승 가능", "en": "Delivery & shipping costs may rise"},
    "GOLD":    {"ko": "안전자산 선호 강화 중", "en": "Safe-haven demand rising"},
    "SILVER":  {"ko": "안전자산 선호 강화 중", "en": "Safe-haven demand rising"},
    "JET_FUEL": {"ko": "항공요금에 영향이 올 수 있어요", "en": "Flight prices may be affected"},
}

# ── 원자재 심볼 → Wallet 카테고리 매핑 ──────────────────────────────
SYMBOL_TO_WALLET = {
    "WTI": "energy", "BRENT": "energy", "NATGAS": "energy", "JET_FUEL": "energy",
    "WHEAT": "food", "CORN": "food", "RICE": "food", "SOYBEAN": "food",
    "BDRY": "energy",  # 해운은 에너지/물류에 영향
    "GOLD": "finance", "SILVER": "finance",
}

# ── Wallet 카테고리 라벨 ─────────────────────────────────────────
WALLET_LABELS: dict[str, dict[str, str]] = {
    "energy":  {"ko": "에너지", "en": "Energy", "emoji": "⛽"},
    "food":    {"ko": "식품", "en": "Groceries", "emoji": "🌾"},
    "finance": {"ko": "금융", "en": "Investments", "emoji": "📈"},
    "travel":  {"ko": "여행", "en": "Travel", "emoji": "✈️"},
}

# ── Wallet Line 매핑 (원자재별 → 1줄 지갑 영향) ──────────────────────
WALLET_LINE_MAP: dict[str, dict[str, str]] = {
    "WTI":     {"ko": "기름값·물가 오를 수 있어요", "en": "Gas & prices may rise"},
    "BRENT":   {"ko": "기름값·물가 오를 수 있어요", "en": "Gas & prices may rise"},
    "WHEAT":   {"ko": "장바구니 물가 주의", "en": "Grocery prices to watch"},
    "CORN":    {"ko": "장바구니 물가 주의", "en": "Grocery prices to watch"},
    "RICE":    {"ko": "장바구니 물가 주의", "en": "Grocery prices to watch"},
    "SOYBEAN": {"ko": "장바구니 물가 주의", "en": "Grocery prices to watch"},
    "NATGAS":  {"ko": "가스비·난방비 오를 수 있어요", "en": "Gas & heating costs may rise"},
    "BDRY":    {"ko": "배달비·물류비 상승 가능", "en": "Delivery & shipping costs may rise"},
    "JET_FUEL": {"ko": "항공요금 인상 가능", "en": "Flight prices may increase"},
    "GOLD":    {"ko": "안전자산 선호 강화 중", "en": "Safe-haven demand rising"},
}

# ── 국가 → 원자재 매핑 (impact.py의 _COUNTRY_COMMODITY_MAP에서 공유) ────
COUNTRY_COMMODITY_MAP: dict[str, dict] = {
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
    "SA": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "AE": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "IQ": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "KW": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "IR": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "LY": {"symbols": ["WTI", "BRENT"], "ko": "원유", "en": "crude oil"},
    "QA": {"symbols": ["NATGAS"], "ko": "천연가스", "en": "natural gas"},
    "NO": {"symbols": ["NATGAS"], "ko": "천연가스", "en": "natural gas"},
    "EG": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
    "PA": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
    "YE": {"symbols": ["BDRY", "WTI"], "ko": "해운·유가", "en": "shipping & oil"},
    "SO": {"symbols": ["BDRY"], "ko": "해운", "en": "shipping"},
}

# ── 5단계 Weather 시스템 ────────────────────────────────────────────
WEATHER_LEVELS = [
    (80, "#991B1B", "🌪️", "위험", "Critical"),
    (60, "#EF4444", "⛈️", "주의", "Elevated"),
    (40, "#F97316", "🌥️", "관심", "Watch"),
    (20, "#EAB308", "⛅",  "양호", "Fair"),
    (0,  "#22C55E", "☀️", "안정", "Clear"),
]


def get_weather(score: int) -> dict:
    """5단계 weather 정보 반환."""
    for threshold, color, emoji, label_ko, label_en in WEATHER_LEVELS:
        if score >= threshold:
            return {
                "color": color, "emoji": emoji,
                "label_ko": label_ko, "label_en": label_en,
            }
    return {"color": "#22C55E", "emoji": "☀️", "label_ko": "안정", "label_en": "Clear"}


# ── Trust Level 4단계 ───────────────────────────────────────────────

def compute_trust_level(
    signal_corroboration_count: int,
    signal_types: list[str] | None,
    independent_sources: int = 0,
) -> tuple[str, str | None]:
    """Trust Level 계산: (level, detail)."""
    count = max(signal_corroboration_count, independent_sources)
    has_sensor = bool(signal_types)

    if count >= 5 and has_sensor:
        return "confirmed", f"Confirmed by {count} sources + satellite"
    if count >= 3:
        return "verified", f"Verified by {count} independent sources"
    if count >= 1:
        return "reported", "Reported. Awaiting further confirmation."
    return "unconfirmed", None


# ── Sensor Context 자연어 ───────────────────────────────────────────

def build_sensor_context(signal_types: list[str] | None, lang: str) -> str | None:
    """센서 데이터 → 자연어 1줄."""
    if not signal_types:
        return None
    parts: list[str] = []
    if "firms" in signal_types:
        parts.append("위성이 열점을 감지했어요" if lang == "ko" else "Satellite detected fire hotspots")
    if "ioda" in signal_types:
        parts.append("인터넷이 끊겼어요" if lang == "ko" else "Internet disrupted")
    if "gps_jam" in signal_types:
        parts.append("GPS 교란 감지" if lang == "ko" else "GPS disruption detected")
    if "cf_radar" in signal_types:
        parts.append("트래픽 이상 감지" if lang == "ko" else "Traffic anomaly detected")
    return " · ".join(parts) if parts else None


# ── Consumer Fields 생성 (what/so_what/when/wallet) ─────────────────

def build_consumer_fields(
    cluster,
    lang: str,
    commodity_prices: dict[str, tuple[float, float]] | None = None,
) -> dict:
    """Consumer 필드 생성. impact.py의 _build_smart_summary() 뒤에 호출."""
    cc = cluster.country_code or ""
    topic = cluster.topic or "unknown"
    severity = cluster.severity or 0

    c_name = cluster.title_ko if lang == "ko" and hasattr(cluster, "title_ko") and cluster.title_ko else cluster.title or ""
    c_name = c_name[:40]

    # ── what_consumer: 구어체 1줄 헤드라인 ──
    _level_ko = "위험" if severity >= 80 else "주의" if severity >= 60 else "관심" if severity >= 40 else "참고"
    _level_en = "Critical" if severity >= 80 else "Elevated" if severity >= 60 else "Watch" if severity >= 40 else "Note"
    what_consumer = c_name if len(c_name) < 40 else c_name[:37] + "..."

    # ── so_what_consumer: 생활 영향 (방향성만) ──
    so_what_consumer = None
    country_map = COUNTRY_COMMODITY_MAP.get(cc)
    if country_map:
        for sym in country_map["symbols"]:
            if sym in COMMODITY_CONSUMER_MAP:
                so_what_consumer = COMMODITY_CONSUMER_MAP[sym][lang]
                break

    if not so_what_consumer:
        # 원유 관련 분쟁이면 에너지 기본값
        if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY", "YE"):
            so_what_consumer = COMMODITY_CONSUMER_MAP["WTI"][lang]
        # 해상 분쟁
        elif topic == "maritime" or cc in ("EG", "PA", "SO", "YE"):
            so_what_consumer = COMMODITY_CONSUMER_MAP["BDRY"][lang]

    # ── when_consumer: 구어체 시간 ──
    if severity >= 80:
        when_consumer = "바로 영향이 올 수 있어요" if lang == "ko" else "Impact could be immediate"
    elif severity >= 60:
        when_consumer = "1~2주 안에 느낄 수 있어요" if lang == "ko" else "You may feel it in 1-2 weeks"
    elif severity >= 40:
        when_consumer = "한두 달 추이를 지켜봐야 해요" if lang == "ko" else "Worth watching over 1-2 months"
    else:
        when_consumer = "직접적 영향은 제한적이에요" if lang == "ko" else "Direct impact is limited"

    # ── wallet_line: 지갑 영향 1줄 ──
    wallet_line = None
    if country_map:
        for sym in country_map["symbols"]:
            if sym in WALLET_LINE_MAP:
                wallet_line = WALLET_LINE_MAP[sym][lang]
                break
    if not wallet_line and so_what_consumer:
        # so_what_consumer가 있으면 첫 번째 관련 원자재 wallet_line
        if topic in ("conflict", "terror") and cc in ("SA", "AE", "IQ", "KW", "IR", "RU", "LY", "YE"):
            wallet_line = WALLET_LINE_MAP.get("WTI", {}).get(lang)
        elif topic == "maritime" or cc in ("EG", "PA", "SO", "YE"):
            wallet_line = WALLET_LINE_MAP.get("BDRY", {}).get(lang)

    # ── trust_level + sensor_context ──
    sig_count = getattr(cluster, "signal_corroboration_count", 0) or 0
    sig_types = getattr(cluster, "signal_types", None) or []
    ind_sources = getattr(cluster, "independent_sources", 0) or 0

    trust_level, trust_detail = compute_trust_level(sig_count, sig_types, ind_sources)
    sensor_context = build_sensor_context(sig_types, lang)

    # verification_label
    if lang == "ko":
        _vl = {"confirmed": "복수 검증 완료", "verified": "검증됨", "reported": "보도됨", "unconfirmed": "미확인"}
    else:
        _vl = {"confirmed": "Multi-source verified", "verified": "Verified", "reported": "Reported", "unconfirmed": "Unconfirmed"}
    verification_label = _vl.get(trust_level, trust_level)

    return {
        "what_consumer": what_consumer,
        "so_what_consumer": so_what_consumer,
        "when_consumer": when_consumer,
        "wallet_line": wallet_line,
        "trust_level": trust_level,
        "trust_detail": trust_detail,
        "sensor_context": sensor_context,
        "verification_label": verification_label,
        "signal_corroboration_count": sig_count,
        "signal_types": list(sig_types),
    }


def compute_wallet_gauges(
    top_issues: list,
    commodity_prices: dict[str, tuple[float, float]],
    travel_advisory_count: int = 0,
) -> dict:
    """Wallet Gauge 4카테고리 0-5 dots 계산."""
    energy_score = 0
    food_score = 0
    finance_score = 0

    for issue in top_issues:
        rc = getattr(issue, "relevant_commodities", None) or []
        impact = getattr(issue, "impact_score", 0) or 0
        for sym in rc:
            cat = SYMBOL_TO_WALLET.get(sym)
            if cat == "energy":
                energy_score += 1
            elif cat == "food":
                food_score += 1
            elif cat == "finance":
                finance_score += 1

    # 가격 변동 추가 가산
    oil_chg = abs(commodity_prices.get("WTI", (0, 0))[1])
    if oil_chg > 15:
        energy_score += 2
    elif oil_chg > 5:
        energy_score += 1

    grain_chg = max(
        abs(commodity_prices.get("WHEAT", (0, 0))[1]),
        abs(commodity_prices.get("CORN", (0, 0))[1]),
        abs(commodity_prices.get("RICE", (0, 0))[1]),
    )
    if grain_chg > 10:
        food_score += 2
    elif grain_chg > 5:
        food_score += 1

    # 금융: 고영향 이슈 수
    high_impact = sum(1 for i in top_issues if (getattr(i, "impact_score", 0) or 0) >= 50)
    finance_score += high_impact

    # 여행: 여행경보 레벨 3+ 수
    travel_score = min(5, travel_advisory_count)

    return {
        "wallet_energy": min(5, energy_score),
        "wallet_food": min(5, food_score),
        "wallet_finance": min(5, finance_score),
        "wallet_travel": travel_score,
    }


def build_commodity_snapshot(
    commodity_prices: dict[str, tuple[float, float]],
) -> dict | None:
    """WalletGauge용 원자재 스냅샷."""
    if not commodity_prices:
        return None

    snap: dict = {}
    # Oil (WTI 우선, BRENT 폴백)
    for sym in ("WTI", "BRENT"):
        if sym in commodity_prices:
            p, c = commodity_prices[sym]
            snap["oil"] = {"price": round(p, 2), "change_pct": round(c, 1), "symbol": sym}
            break

    # Wheat
    if "WHEAT" in commodity_prices:
        p, c = commodity_prices["WHEAT"]
        snap["wheat"] = {"price": round(p, 2), "change_pct": round(c, 1), "symbol": "ZW=F"}

    # Shipping
    if "BDRY" in commodity_prices:
        p, c = commodity_prices["BDRY"]
        snap["shipping"] = {"price": round(p, 2), "change_pct": round(c, 1), "symbol": "BDRY"}

    # Natural Gas
    if "NATGAS" in commodity_prices:
        p, c = commodity_prices["NATGAS"]
        snap["natgas"] = {"price": round(p, 2), "change_pct": round(c, 1), "symbol": "NG=F"}

    # Gold
    if "GOLD" in commodity_prices:
        p, c = commodity_prices["GOLD"]
        snap["gold"] = {"price": round(p, 2), "change_pct": round(c, 1), "symbol": "GC=F"}

    return snap if snap else None
