"""
경제 데이터 수집기 — Tier 2 데이터 파이프라인

1. IMF IMTS (International Merchandise Trade Statistics)
   - 양자간 교역 데이터 (월간/연간)
   - 무료, 인증 불필요
   - API: https://data.imf.org/api/v1/data/DOT/

2. World Bank Indicators
   - GDP, GDP per capita, 교역 의존도 등
   - 무료, CC BY 4.0
   - API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}

3. Frankfurter Exchange Rates
   - ECB 기반 환율 (USD 기준)
   - 무료, 무제한, 인증 불필요
   - API: https://api.frankfurter.dev/

수집 주기: 1일 1회 (Worker cron)
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── 대상 국가 (SECTOR_DATA에 있는 20개국 + 주요 교역 파트너) ──────────────
TARGET_COUNTRIES = [
    "KR", "US", "JP", "CN", "DE", "GB", "FR", "AU", "IN", "BR",
    "SA", "AE", "IL", "TR", "TW", "TH", "VN", "SG", "CA", "MX",
    "RU", "UA", "IR", "IQ", "PK", "ID", "PH", "MY", "NL", "IT",
]

# IMF DOTS country code 매핑 (ISO alpha-2 → IMF numeric)
# IMF uses ISO 3166-1 alpha-2 for most, but some need mapping
IMF_COUNTRY_MAP = {
    "KR": "542", "US": "111", "JP": "158", "CN": "924", "DE": "134",
    "GB": "112", "FR": "132", "AU": "193", "IN": "534", "BR": "223",
    "SA": "456", "AE": "466", "IL": "436", "TR": "186", "TW": "528",
    "TH": "578", "VN": "582", "SG": "576", "CA": "156", "MX": "273",
    "RU": "922", "UA": "926", "IR": "429", "IQ": "433", "PK": "564",
    "ID": "536", "PH": "566", "MY": "548", "NL": "138", "IT": "136",
}

# World Bank 경제 지표 코드
WB_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "BN.CAB.XOKA.CD": "Current account balance (BoP, current US$)",
}

# 주요 교역 파트너 (각 국가당 상위 5개)
# IMF API에서 가져올 reporter-partner 쌍
TRADE_PAIRS = {
    "KR": ["CN", "US", "JP", "VN", "TW"],
    "US": ["CN", "MX", "CA", "JP", "DE"],
    "JP": ["CN", "US", "KR", "TW", "TH"],
    "CN": ["US", "JP", "KR", "VN", "DE"],
    "DE": ["US", "CN", "FR", "NL", "IT"],
    "GB": ["US", "DE", "NL", "FR", "CN"],
    "FR": ["DE", "US", "IT", "ES", "BE"],
    "AU": ["CN", "JP", "KR", "US", "IN"],
    "IN": ["US", "CN", "AE", "SA", "SG"],
    "BR": ["CN", "US", "AR", "NL", "DE"],
    "SA": ["CN", "IN", "JP", "KR", "US"],
    "AE": ["IN", "CN", "JP", "US", "SA"],
    "IL": ["US", "CN", "DE", "GB", "IN"],
    "TR": ["DE", "US", "GB", "IT", "IQ"],
    "TW": ["CN", "US", "JP", "KR", "SG"],
    "TH": ["CN", "US", "JP", "VN", "MY"],
    "VN": ["US", "CN", "KR", "JP", "TH"],
    "SG": ["CN", "MY", "US", "ID", "JP"],
    "CA": ["US", "CN", "GB", "JP", "MX"],
    "MX": ["US", "CN", "CA", "DE", "JP"],
}


async def _fetch_json(session: aiohttp.ClientSession, url: str, params: dict | None = None) -> dict | None:
    """HTTP GET + JSON 파싱 (에러 시 None 반환)"""
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("HTTP %d from %s", resp.status, url)
                return None
            return await resp.json(content_type=None)
    except Exception as e:
        logger.error("fetch_error url=%s err=%s", url, str(e))
        return None


# ── 1. IMF IMTS 양자간 교역 수집 ─────────────────────────────────────────

async def collect_imf_trade(db: AsyncSession) -> int:
    """IMF DOTS API로 양자간 교역 데이터 수집 (연간, 최근 3년)

    API 형식: https://data.imf.org/api/v1/data/DOT/A.{reporter}.TXG_FOB_USD.{partner}
    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import TradeBilateral

    saved = 0
    current_year = datetime.now(timezone.utc).year
    years = [str(y) for y in range(current_year - 3, current_year)]

    async with aiohttp.ClientSession() as session:
        for reporter, partners in TRADE_PAIRS.items():
            reporter_imf = IMF_COUNTRY_MAP.get(reporter)
            if not reporter_imf:
                continue

            for partner in partners:
                partner_imf = IMF_COUNTRY_MAP.get(partner)
                if not partner_imf:
                    continue

                # 이미 있는지 확인 (중복 방지)
                existing = await db.execute(
                    select(TradeBilateral.id).where(
                        and_(
                            TradeBilateral.reporter_code == reporter,
                            TradeBilateral.partner_code == partner,
                            TradeBilateral.period == years[-1],
                        )
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                # Export (FOB)
                export_url = f"https://data.imf.org/api/v1/data/DOT/A.{reporter_imf}.TXG_FOB_USD.{partner_imf}"
                export_data = await _fetch_json(session, export_url, {
                    "startPeriod": years[0],
                    "endPeriod": years[-1],
                })

                # Import (CIF)
                import_url = f"https://data.imf.org/api/v1/data/DOT/A.{reporter_imf}.TMG_CIF_USD.{partner_imf}"
                import_data = await _fetch_json(session, import_url, {
                    "startPeriod": years[0],
                    "endPeriod": years[-1],
                })

                export_by_year = _parse_imf_series(export_data)
                import_by_year = _parse_imf_series(import_data)

                for year in years:
                    exp_val = export_by_year.get(year)
                    imp_val = import_by_year.get(year)
                    if exp_val is None and imp_val is None:
                        continue

                    total = (exp_val or 0) + (imp_val or 0)
                    record = TradeBilateral(
                        reporter_code=reporter,
                        partner_code=partner,
                        period=year,
                        period_type="A",
                        export_value_usd=exp_val,
                        import_value_usd=imp_val,
                        total_trade_usd=total if total > 0 else None,
                        source="imf_imts",
                    )
                    db.add(record)
                    saved += 1

                # Rate limiting: 0.5초 간격
                await asyncio.sleep(0.5)

        await db.flush()

    logger.info("imf_trade_collected count=%d", saved)
    return saved


def _parse_imf_series(data: dict | None) -> dict[str, float]:
    """IMF JSON-stat 응답에서 {year: value_millions} 딕셔너리 추출"""
    result = {}
    if not data:
        return result
    try:
        # IMF SDMX-JSON 형식
        datasets = data.get("dataSets", [{}])
        if not datasets:
            return result
        series = datasets[0].get("series", {})
        # time dimensions
        structure = data.get("structure", {}).get("dimensions", {}).get("observation", [])
        time_periods = []
        for dim in structure:
            if dim.get("id") == "TIME_PERIOD":
                time_periods = [v.get("id", "") for v in dim.get("values", [])]
                break

        for _, s in series.items():
            obs = s.get("observations", {})
            for idx_str, values in obs.items():
                idx = int(idx_str)
                if idx < len(time_periods) and values and values[0] is not None:
                    result[time_periods[idx]] = values[0]  # already in millions USD
    except Exception as e:
        logger.error("imf_parse_error: %s", str(e))
    return result


# ── 2. World Bank 경제 지표 수집 ──────────────────────────────────────────

async def collect_world_bank_indicators(db: AsyncSession) -> int:
    """World Bank API로 주요 경제 지표 수집 (최근 5년)

    API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}
    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import EconomicIndicator

    saved = 0
    current_year = datetime.now(timezone.utc).year

    async with aiohttp.ClientSession() as session:
        for indicator_code, indicator_name in WB_INDICATORS.items():
            # World Bank는 세미콜론으로 여러 국가 배치 조회 가능
            country_str = ";".join(TARGET_COUNTRIES)
            url = f"https://api.worldbank.org/v2/country/{country_str}/indicator/{indicator_code}"
            params = {
                "format": "json",
                "per_page": "500",
                "date": f"{current_year - 5}:{current_year}",
            }

            data = await _fetch_json(session, url, params)
            if not data or len(data) < 2:
                continue

            records = data[1] if isinstance(data, list) and len(data) > 1 else []

            for rec in records:
                if not rec or rec.get("value") is None:
                    continue

                cc = rec.get("countryiso3code", "")
                # ISO alpha-3 → alpha-2 변환 (World Bank는 alpha-3 사용)
                cc2 = _iso3_to_iso2(cc)
                if not cc2 or cc2 not in TARGET_COUNTRIES:
                    continue

                year = int(rec.get("date", "0"))
                value = float(rec["value"])

                # 중복 확인
                existing = await db.execute(
                    select(EconomicIndicator.id).where(
                        and_(
                            EconomicIndicator.country_code == cc2,
                            EconomicIndicator.indicator_code == indicator_code,
                            EconomicIndicator.year == year,
                        )
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(EconomicIndicator(
                    country_code=cc2,
                    indicator_code=indicator_code,
                    indicator_name=indicator_name,
                    year=year,
                    value=value,
                    source="world_bank",
                ))
                saved += 1

            await asyncio.sleep(0.3)

        await db.flush()

    logger.info("world_bank_collected count=%d", saved)
    return saved


# ISO 3166-1 alpha-3 → alpha-2 매핑 (주요 국가)
_ISO3_TO_ISO2 = {
    "KOR": "KR", "USA": "US", "JPN": "JP", "CHN": "CN", "DEU": "DE",
    "GBR": "GB", "FRA": "FR", "AUS": "AU", "IND": "IN", "BRA": "BR",
    "SAU": "SA", "ARE": "AE", "ISR": "IL", "TUR": "TR", "TWN": "TW",
    "THA": "TH", "VNM": "VN", "SGP": "SG", "CAN": "CA", "MEX": "MX",
    "RUS": "RU", "UKR": "UA", "IRN": "IR", "IRQ": "IQ", "PAK": "PK",
    "IDN": "ID", "PHL": "PH", "MYS": "MY", "NLD": "NL", "ITA": "IT",
}


def _iso3_to_iso2(alpha3: str) -> str | None:
    return _ISO3_TO_ISO2.get(alpha3)


# ── 3. Frankfurter 환율 수집 ──────────────────────────────────────────────

# 주요 통화 (SECTOR_DATA 국가 통화)
TARGET_CURRENCIES = [
    "KRW", "JPY", "CNY", "EUR", "GBP", "AUD", "INR", "BRL",
    "SAR", "AED", "ILS", "TRY", "THB", "VND", "SGD", "CAD", "MXN", "RUB",
]


async def collect_exchange_rates(db: AsyncSession) -> int:
    """Frankfurter API로 USD 기준 환율 수집

    API: https://api.frankfurter.dev/latest?base=USD&symbols=KRW,JPY,...
    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import ExchangeRate

    saved = 0
    symbols = ",".join(TARGET_CURRENCIES)

    async with aiohttp.ClientSession() as session:
        # Frankfurter API: api.frankfurter.app (primary) or api.frankfurter.dev
        url = f"https://api.frankfurter.app/latest?base=USD&symbols={symbols}"
        data = await _fetch_json(session, url)
        if not data or "rates" not in data:
            logger.error("frankfurter_error: no rates")
            return 0

        rate_date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        for currency, rate in data["rates"].items():
            # 중복 확인
            existing = await db.execute(
                select(ExchangeRate.id).where(
                    and_(
                        ExchangeRate.base_currency == "USD",
                        ExchangeRate.target_currency == currency,
                        ExchangeRate.rate_date == rate_date,
                    )
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                continue

            db.add(ExchangeRate(
                base_currency="USD",
                target_currency=currency,
                rate_date=rate_date,
                rate=float(rate),
            ))
            saved += 1

        await db.flush()

    logger.info("exchange_rates_collected count=%d date=%s", saved, rate_date)
    return saved


# ── 통합 수집 함수 ────────────────────────────────────────────────────────

async def collect_all_economic_data(db: AsyncSession) -> dict:
    """모든 경제 데이터 수집 (1일 1회 cron으로 호출)"""
    results = {}

    try:
        results["exchange_rates"] = await collect_exchange_rates(db)
    except Exception as e:
        logger.error("exchange_rate_collection_failed: %s", str(e))
        results["exchange_rates"] = -1

    try:
        results["world_bank"] = await collect_world_bank_indicators(db)
    except Exception as e:
        logger.error("world_bank_collection_failed: %s", str(e))
        results["world_bank"] = -1

    try:
        results["imf_trade"] = await collect_imf_trade(db)
    except Exception as e:
        logger.error("imf_trade_collection_failed: %s", str(e))
        results["imf_trade"] = -1

    await db.commit()
    logger.info("economic_data_collection_complete results=%s", results)
    return results
