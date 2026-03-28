"""
경제 데이터 수집기 — Tier 2 데이터 파이프라인

1. IMF IMTS (International Merchandise Trade Statistics)
   - 양자간 교역 데이터 (월간/연간)
   - 무료, 인증 불필요
   - SDMX 2.1 API: https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IMTS,1.0.0/
   - 국가 코드: ISO alpha-3 (KOR, USA, JPN 등)
   - 지표: XG_FOB_USD (수출), MG_CIF_USD (수입)

2. World Bank Indicators
   - GDP, GDP per capita, 교역 의존도 등
   - 무료, CC BY 4.0
   - API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}

3. Frankfurter Exchange Rates
   - ECB 기반 환율 (USD 기준)
   - 무료, 무제한, 인증 불필요
   - API: https://api.frankfurter.app/

수집 주기: 1일 1회 (Worker cron)
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
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

# IMF IMTS SDMX 국가 코드 매핑 (ISO alpha-2 → ISO alpha-3)
# IMF IMTS API는 ISO 3166-1 alpha-3 코드 사용
IMF_COUNTRY_MAP = {
    "KR": "KOR", "US": "USA", "JP": "JPN", "CN": "CHN", "DE": "DEU",
    "GB": "GBR", "FR": "FRA", "AU": "AUS", "IN": "IND", "BR": "BRA",
    "SA": "SAU", "AE": "ARE", "IL": "ISR", "TR": "TUR", "TW": "TWN",
    "TH": "THA", "VN": "VNM", "SG": "SGP", "CA": "CAN", "MX": "MEX",
    "RU": "RUS", "UA": "UKR", "IR": "IRN", "IQ": "IRQ", "PK": "PAK",
    "ID": "IDN", "PH": "PHL", "MY": "MYS", "NL": "NLD", "IT": "ITA",
    "ES": "ESP", "BE": "BEL", "AR": "ARG", "NZ": "NZL", "QA": "QAT",
    "KW": "KWT", "NO": "NOR", "PL": "POL", "IE": "IRL", "HK": "HKG",
    "EG": "EGY",
}

# World Bank 경제 지표 코드
WB_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "BN.CAB.XOKA.CD": "Current account balance (BoP, current US$)",
}

# 주요 교역 파트너 (각 국가당 상위 15개)
# IMF API에서 가져올 reporter-partner 쌍
TRADE_PAIRS = {
    "KR": ["CN", "US", "JP", "VN", "TW", "SA", "AE", "DE", "AU", "IN", "SG", "ID", "MY", "IQ", "RU"],
    "US": ["CN", "MX", "CA", "JP", "DE", "KR", "GB", "IN", "TW", "VN", "FR", "IT", "BR", "SA", "IE"],
    "JP": ["CN", "US", "KR", "TW", "TH", "AU", "AE", "SA", "DE", "VN", "ID", "MY", "SG", "IN", "FR"],
    "CN": ["US", "JP", "KR", "VN", "DE", "TW", "AU", "MY", "BR", "RU", "TH", "IN", "SG", "ID", "SA"],
    "DE": ["US", "CN", "FR", "NL", "IT", "PL", "GB", "BE", "AU", "ES", "TR", "JP", "KR", "RU", "IN"],
    "GB": ["US", "DE", "NL", "FR", "CN", "IE", "BE", "IT", "ES", "NO", "IN", "TR", "JP", "SA", "AE"],
    "FR": ["DE", "US", "IT", "ES", "BE", "GB", "NL", "CN", "PL", "SA", "IN", "TR", "JP", "AE", "IE"],
    "AU": ["CN", "JP", "KR", "US", "IN", "SG", "NZ", "TH", "MY", "DE", "GB", "TW", "ID", "SA", "AE"],
    "IN": ["US", "CN", "AE", "SA", "SG", "IQ", "ID", "KR", "JP", "DE", "MY", "AU", "GB", "TH", "QA"],
    "BR": ["CN", "US", "AR", "NL", "DE", "IN", "JP", "KR", "SG", "MX", "SA", "IT", "FR", "AE", "ID"],
    "SA": ["CN", "IN", "JP", "KR", "US", "AE", "SG", "EG", "DE", "TR", "PK", "IT", "FR", "TH", "ID"],
    "AE": ["IN", "CN", "JP", "US", "SA", "KR", "TR", "DE", "IQ", "TH", "SG", "EG", "GB", "IT", "ID"],
    "IL": ["US", "CN", "DE", "GB", "IN", "TR", "NL", "IT", "BE", "FR", "JP", "KR", "AE", "TW", "ES"],
    "TR": ["DE", "US", "GB", "IT", "IQ", "CN", "RU", "FR", "ES", "NL", "AE", "SA", "IN", "EG", "KR"],
    "TW": ["CN", "US", "JP", "KR", "SG", "MY", "VN", "DE", "TH", "IN", "NL", "ID", "AU", "SA", "AE"],
    "TH": ["CN", "US", "JP", "VN", "MY", "SG", "IN", "AU", "ID", "KR", "AE", "SA", "DE", "TW", "GB"],
    "VN": ["US", "CN", "KR", "JP", "TH", "TW", "IN", "DE", "MY", "ID", "AU", "SG", "SA", "AE", "GB"],
    "SG": ["CN", "MY", "US", "ID", "JP", "TW", "KR", "HK", "TH", "IN", "AU", "DE", "VN", "SA", "AE"],
    "CA": ["US", "CN", "GB", "JP", "MX", "DE", "KR", "FR", "IT", "IN", "SA", "NO", "AU", "NL", "TW"],
    "MX": ["US", "CN", "CA", "DE", "JP", "KR", "BR", "IT", "MY", "IN", "FR", "TW", "NL", "SA", "GB"],
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

async def _fetch_xml(session: aiohttp.ClientSession, url: str) -> str | None:
    """HTTP GET + XML 텍스트 반환 (에러 시 None)"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as resp:
            if resp.status != 200:
                logger.warning("HTTP %d from %s", resp.status, url)
                return None
            return await resp.text()
    except Exception as e:
        logger.error("fetch_xml_error url=%s err=%s", url, str(e))
        return None


def _parse_imf_sdmx_xml(xml_text: str) -> dict[str, float]:
    """IMF SDMX 2.1 XML 응답에서 {year: value_usd} 딕셔너리 추출.

    응답 형식: <Series ...><Obs TIME_PERIOD="2023" OBS_VALUE="12345678"/></Series>
    """
    result = {}
    if not xml_text:
        return result
    try:
        root = ET.fromstring(xml_text)
        # 네임스페이스 무시하고 모든 Obs 태그 검색
        for elem in root.iter():
            if elem.tag.endswith("}Obs") or elem.tag == "Obs":
                period = elem.get("TIME_PERIOD", "")
                value_str = elem.get("OBS_VALUE", "")
                if period and value_str:
                    try:
                        result[period] = float(value_str)
                    except ValueError:
                        pass
    except ET.ParseError as e:
        logger.error("imf_xml_parse_error: %s", str(e))
    except Exception as e:
        logger.error("imf_parse_error: %s", str(e))
    return result


async def collect_imf_trade(db: AsyncSession) -> int:
    """IMF IMTS SDMX 2.1 API로 양자간 교역 데이터 수집 (연간, 최근 3년)

    API: https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IMTS,1.0.0/{reporter}.{indicator}.{partner}.A
    지표: XG_FOB_USD (수출 FOB), MG_CIF_USD (수입 CIF)
    국가 코드: ISO alpha-3 (KOR, USA 등)
    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import TradeBilateral

    IMF_BASE = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IMTS,1.0.0"
    saved = 0
    current_year = datetime.now(timezone.utc).year
    start_year = current_year - 3
    end_year = current_year - 1  # 당해는 보통 미완성

    async with aiohttp.ClientSession() as session:
        for reporter, partners in TRADE_PAIRS.items():
            reporter_a3 = IMF_COUNTRY_MAP.get(reporter)
            if not reporter_a3:
                continue

            for partner in partners:
                partner_a3 = IMF_COUNTRY_MAP.get(partner)
                if not partner_a3:
                    continue

                # 이미 최신 데이터가 있는지 확인 (중복 방지)
                existing = await db.execute(
                    select(TradeBilateral.id).where(
                        and_(
                            TradeBilateral.reporter_code == reporter,
                            TradeBilateral.partner_code == partner,
                            TradeBilateral.period == str(end_year),
                        )
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                # Export (FOB) — XML 응답
                export_url = (
                    f"{IMF_BASE}/{reporter_a3}.XG_FOB_USD.{partner_a3}.A"
                    f"?startPeriod={start_year}&endPeriod={end_year}"
                )
                export_xml = await _fetch_xml(session, export_url)
                export_by_year = _parse_imf_sdmx_xml(export_xml)

                # Import (CIF)
                import_url = (
                    f"{IMF_BASE}/{reporter_a3}.MG_CIF_USD.{partner_a3}.A"
                    f"?startPeriod={start_year}&endPeriod={end_year}"
                )
                import_xml = await _fetch_xml(session, import_url)
                import_by_year = _parse_imf_sdmx_xml(import_xml)

                for year in range(start_year, end_year + 1):
                    y = str(year)
                    exp_val = export_by_year.get(y)
                    imp_val = import_by_year.get(y)
                    if exp_val is None and imp_val is None:
                        continue

                    total = (exp_val or 0) + (imp_val or 0)
                    record = TradeBilateral(
                        reporter_code=reporter,
                        partner_code=partner,
                        period=y,
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
    "ESP": "ES", "BEL": "BE", "ARG": "AR", "NZL": "NZ", "QAT": "QA",
    "KWT": "KW", "NOR": "NO", "POL": "PL", "IRL": "IE", "HKG": "HK",
    "EGY": "EG",
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

    API: https://api.frankfurter.app/latest?base=USD&symbols=KRW,JPY,...
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


# ── 4. yfinance 원자재 가격 수집 ─────────────────────────────────────────

COMMODITY_TICKERS = {
    # 에너지
    "WTI": ("CL=F", "WTI Crude Oil"),
    "BRENT": ("BZ=F", "Brent Crude Oil"),
    "NATGAS": ("NG=F", "Natural Gas"),
    # 곡물/식량
    "WHEAT": ("ZW=F", "Wheat Futures"),
    "CORN": ("ZC=F", "Corn Futures"),
    "SOYBEAN": ("ZS=F", "Soybean Futures"),
    "RICE": ("ZR=F", "Rough Rice Futures"),
    # 금속/안전자산
    "GOLD": ("GC=F", "Gold"),
    "SILVER": ("SI=F", "Silver"),
    # 해운 (BDI proxy)
    "BDRY": ("BDRY", "Breakwave Dry Bulk Shipping ETF"),
}


async def collect_commodity_prices(db: AsyncSession) -> int:
    """yfinance로 원자재 가격 수집 (WTI, Brent, Gold).

    yfinance는 동기 라이브러리이므로 asyncio.to_thread로 실행.
    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import CommodityPrice

    saved = 0

    def _fetch_yf():
        """동기 yfinance 호출 (스레드에서 실행)"""
        import yfinance as yf
        results = {}
        for symbol, (ticker, name) in COMMODITY_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if hist.empty or len(hist) < 1:
                    continue
                close_today = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    close_prev = float(hist["Close"].iloc[-2])
                    change_pct = ((close_today - close_prev) / close_prev) * 100 if close_prev else 0
                else:
                    change_pct = 0
                price_date = hist.index[-1].strftime("%Y-%m-%d")
                results[symbol] = {
                    "name": name,
                    "price_usd": round(close_today, 2),
                    "change_pct": round(change_pct, 2),
                    "price_date": price_date,
                }
            except Exception as e:
                logger.warning("yfinance_commodity_error symbol=%s err=%s", symbol, str(e))
        return results

    try:
        data = await asyncio.to_thread(_fetch_yf)
    except Exception as e:
        logger.error("yfinance_thread_error: %s", str(e))
        return 0

    for symbol, info in data.items():
        # 중복 확인
        existing = await db.execute(
            select(CommodityPrice.id).where(
                and_(
                    CommodityPrice.symbol == symbol,
                    CommodityPrice.price_date == info["price_date"],
                )
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        db.add(CommodityPrice(
            symbol=symbol,
            name=info["name"],
            price_usd=info["price_usd"],
            change_pct=info["change_pct"],
            price_date=info["price_date"],
        ))
        saved += 1

    await db.flush()
    logger.info("commodity_prices_collected count=%d", saved)
    return saved


# ── 4b. FRED API 제트연료 수집 ─────────────────────────────────────────────

FRED_API_KEY = None  # 환경변수에서 로드

FRED_SERIES = {
    "JET_FUEL": ("DJFUELUSGULF", "Jet Fuel (US Gulf Coast)"),
}


async def collect_fred_commodities(db: AsyncSession) -> int:
    """FRED API로 제트연료 등 yfinance에 없는 원자재 가격 수집.

    FRED_API_KEY 환경변수 필요 (https://fred.stlouisfed.org/docs/api/api_key.html).
    Returns: 저장된 레코드 수
    """
    import os
    from backend.app.models.economic_data import CommodityPrice

    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        logger.warning("fred_skip: FRED_API_KEY not set")
        return 0

    saved = 0
    async with aiohttp.ClientSession() as session:
        for symbol, (series_id, name) in FRED_SERIES.items():
            try:
                url = (
                    f"https://api.stlouisfed.org/fred/series/observations"
                    f"?series_id={series_id}&api_key={api_key}&file_type=json"
                    f"&sort_order=desc&limit=2"
                )
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("fred_api_error series=%s status=%d", series_id, resp.status)
                        continue
                    data = await resp.json()

                obs = [o for o in data.get("observations", []) if o.get("value", ".") != "."]
                if not obs:
                    continue

                price = float(obs[0]["value"])
                price_date = obs[0]["date"]
                change_pct = 0.0
                if len(obs) >= 2:
                    prev = float(obs[1]["value"])
                    if prev:
                        change_pct = round(((price - prev) / prev) * 100, 2)

                # 중복 확인
                existing = await db.execute(
                    select(CommodityPrice.id).where(
                        and_(
                            CommodityPrice.symbol == symbol,
                            CommodityPrice.price_date == price_date,
                        )
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(CommodityPrice(
                    symbol=symbol,
                    name=name,
                    price_usd=round(price, 2),
                    change_pct=change_pct,
                    price_date=price_date,
                ))
                saved += 1
            except Exception as e:
                logger.warning("fred_commodity_error series=%s err=%s", series_id, str(e))

    await db.flush()
    logger.info("fred_commodities_collected count=%d", saved)
    return saved


# ── 5. yfinance 주요 주가지수 수집 ────────────────────────────────────────

MARKET_INDEX_TICKERS = {
    "KOSPI": ("^KS11", "KOSPI", "KRW"),
    "SPX": ("^GSPC", "S&P 500", "USD"),
    "NKY": ("^N225", "Nikkei 225", "JPY"),
    "DAX": ("^GDAXI", "DAX", "EUR"),
    "FTSE": ("^FTSE", "FTSE 100", "GBP"),
    "SSE": ("000001.SS", "SSE Composite", "CNY"),
}


async def collect_market_indices(db: AsyncSession) -> int:
    """yfinance로 주요 주가지수 수집.

    Returns: 저장된 레코드 수
    """
    from backend.app.models.economic_data import MarketIndex

    saved = 0

    def _fetch_yf():
        import yfinance as yf
        results = {}
        for symbol, (ticker, name, currency) in MARKET_INDEX_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if hist.empty or len(hist) < 1:
                    continue
                close_today = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    close_prev = float(hist["Close"].iloc[-2])
                    change_pct = ((close_today - close_prev) / close_prev) * 100 if close_prev else 0
                else:
                    change_pct = 0
                index_date = hist.index[-1].strftime("%Y-%m-%d")
                results[symbol] = {
                    "name": name,
                    "value": round(close_today, 2),
                    "change_pct": round(change_pct, 2),
                    "index_date": index_date,
                    "currency": currency,
                }
            except Exception as e:
                logger.warning("yfinance_index_error symbol=%s err=%s", symbol, str(e))
        return results

    try:
        data = await asyncio.to_thread(_fetch_yf)
    except Exception as e:
        logger.error("yfinance_index_thread_error: %s", str(e))
        return 0

    for symbol, info in data.items():
        existing = await db.execute(
            select(MarketIndex.id).where(
                and_(
                    MarketIndex.symbol == symbol,
                    MarketIndex.index_date == info["index_date"],
                )
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        db.add(MarketIndex(
            symbol=symbol,
            name=info["name"],
            value=info["value"],
            change_pct=info["change_pct"],
            index_date=info["index_date"],
            currency=info["currency"],
        ))
        saved += 1

    await db.flush()
    logger.info("market_indices_collected count=%d", saved)
    return saved


# ── 6. 구조화된 여행 경보 수집 (US State Dept) ────────────────────────────

# US Advisory Level names
_US_LEVEL_NAMES = {
    1: "Exercise Normal Precautions",
    2: "Exercise Increased Caution",
    3: "Reconsider Travel",
    4: "Do Not Travel",
}

# US State Dept FIPS 10-4 → ISO 3166-1 alpha-2 변환
# API가 FIPS 코드를 사용하므로 ISO로 변환 필요
_FIPS_TO_ISO = {
    "AJ": "AZ", "AS": "AU", "BG": "BD", "BH": "BZ", "BK": "BA",
    "BL": "BO", "BM": "MM", "BN": "BJ", "BO": "BY", "BP": "SB",
    "BU": "BG", "BX": "BN", "BY": "BI", "CB": "KH", "CD": "TD",
    "CE": "LK", "CF": "CG", "CG": "CD", "CH": "CN", "CI": "CL",
    "CN": "KM", "CS": "CR", "CT": "CF", "DA": "DK", "DR": "DO",
    "EI": "IE", "EK": "GQ", "EN": "EE", "ES": "SV", "EZ": "CZ",
    "FP": "PF", "GA": "GM", "GB": "GA", "GG": "GE", "GJ": "GD",
    "GM": "DE", "GV": "GN", "HA": "HT", "HO": "HN", "IC": "IS",
    "IV": "CI", "IZ": "IQ", "JA": "JP", "KN": "KP", "KR": "KI",
    "KS": "KR", "KU": "KW", "KV": "XK", "LE": "LB", "LG": "LV",
    "LH": "LT", "LI": "LR", "LO": "SK", "LT": "LS", "MA": "MG",
    "MG": "MN", "MH": "MS", "MI": "MW", "MJ": "ME", "MO": "MA",
    "MP": "MU", "MU": "OM", "NG": "NE", "NH": "VU", "NI": "NG",
    "NN": "SX", "NS": "SR", "NU": "NI", "OD": "SS", "PA": "PY",
    "PM": "PA", "PO": "PT", "PP": "PG", "PS": "PW", "RI": "RS",
    "RM": "MH", "RP": "PH", "RS": "RU", "SC": "KN", "SE": "SC",
    "SF": "ZA", "SN": "SG", "SP": "ES", "SR": "CH", "ST": "LC",
    "SU": "SD", "SW": "SE", "TD": "TT", "TI": "TJ", "TK": "TC",
    "TN": "TO", "TO": "TG", "TP": "ST", "TS": "TN", "TT": "TL",
    "TU": "TR", "TX": "TM", "UC": "CW", "UK": "GB", "UP": "UA",
    "UV": "BF", "VM": "VN", "WA": "NA", "WZ": "SZ", "ZA": "ZM",
    "ZI": "ZW", "AA": "AW", "AV": "AI", "BD": "BM", "BF": "BS",
    "CJ": "KY", "DO": "DM", "VI": "VG",
}


async def collect_travel_advisories_structured(db: AsyncSession) -> int:
    """US State Department Travel Advisory를 구조화된 형태로 저장.

    기존 travel_advisory.py는 RawEvent로 저장하지만,
    이 함수는 TravelAdvisory 테이블에 country_code + level로 직접 저장.
    Returns: upsert된 레코드 수
    """
    from backend.app.models.economic_data import TravelAdvisory
    import re

    saved = 0
    url = "https://cadataapi.state.gov/api/TravelAdvisories"

    async with aiohttp.ClientSession() as session:
        data = await _fetch_json(session, url)
        if not data:
            logger.error("travel_advisory_structured: no data")
            return 0

        # API 응답 형식: list of advisories
        advisories = data if isinstance(data, list) else data.get("value", data.get("data", []))
        if not isinstance(advisories, list):
            logger.error("travel_advisory_structured: unexpected format")
            return 0

        for adv in advisories:
            # 국가 코드 추출 — API 형식: Category: ["SA"] 또는 iso_code/CountryCode
            cc = adv.get("iso_code") or adv.get("country_iso") or adv.get("CountryCode", "")
            if not cc:
                # Category 배열에서 추출 (US State Dept 실제 API 형식)
                cats = adv.get("Category") or adv.get("category")
                if isinstance(cats, list) and cats:
                    cc = cats[0]
                elif isinstance(cats, str):
                    cc = cats
            if not cc or len(cc) < 2:
                continue

            cc = cc.upper()[:2]
            # FIPS 10-4 → ISO 3166-1 alpha-2 변환
            cc = _FIPS_TO_ISO.get(cc, cc)

            # Level 추출 — API 형식: Title: "Country - Level 3: Reconsider Travel"
            level = adv.get("advisory_level") or adv.get("AdvisoryLevel")
            if level is None:
                title_text = adv.get("Title") or adv.get("advisory_text") or adv.get("title") or ""
                m = re.search(r"Level\s+(\d)", title_text)
                if m:
                    level = int(m.group(1))
                else:
                    continue
            level = int(level)
            if level < 1 or level > 4:
                continue

            title = _US_LEVEL_NAMES.get(level, f"Level {level}")

            # UPSERT: 같은 (country_code, source) 있으면 업데이트
            existing_q = await db.execute(
                select(TravelAdvisory).where(
                    and_(
                        TravelAdvisory.country_code == cc,
                        TravelAdvisory.source == "us_state_dept",
                    )
                ).limit(1)
            )
            existing = existing_q.scalar_one_or_none()
            if existing:
                if existing.level != level:
                    existing.level = level
                    existing.title = title
                    existing.fetched_at = datetime.now(timezone.utc)
                    saved += 1
            else:
                db.add(TravelAdvisory(
                    country_code=cc,
                    level=level,
                    title=title,
                    source="us_state_dept",
                ))
                saved += 1

        await db.flush()

    logger.info("travel_advisories_structured count=%d", saved)
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


async def collect_market_data(db: AsyncSession) -> dict:
    """시장 데이터 수집 — 원자재 + 지수 + 구조화 여행 경보 (6시간마다)"""
    results = {}

    try:
        results["commodities"] = await collect_commodity_prices(db)
    except Exception as e:
        logger.error("commodity_collection_failed: %s", str(e))
        results["commodities"] = -1

    try:
        results["fred_commodities"] = await collect_fred_commodities(db)
    except Exception as e:
        logger.error("fred_commodity_collection_failed: %s", str(e))
        results["fred_commodities"] = -1

    try:
        results["indices"] = await collect_market_indices(db)
    except Exception as e:
        logger.error("index_collection_failed: %s", str(e))
        results["indices"] = -1

    try:
        results["travel_advisories"] = await collect_travel_advisories_structured(db)
    except Exception as e:
        logger.error("travel_advisory_structured_failed: %s", str(e))
        results["travel_advisories"] = -1

    await db.commit()
    logger.info("market_data_collection_complete results=%s", results)
    return results
