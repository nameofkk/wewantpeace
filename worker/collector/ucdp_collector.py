"""
UCDP (Uppsala Conflict Data Program) 역사적 분쟁 데이터 수집기.
매일 1회(06:00 UTC) 실행. 검증된 학술 데이터.
raw_events 파이프라인으로 투입 (signal_points 아님).
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

UCDP_ACCESS_TOKEN = os.environ.get("UCDP_ACCESS_TOKEN", "")
UCDP_API_URL = "https://ucdpapi.pcr.uu.se/api/gedevents/25.1"

# 2010년 이후 데이터만 수집 (적절한 역사적 범위 + API 부하 제한)
START_DATE = "2010-01-01"
MAX_PAGES = 300  # 안전 캡 (pagesize=1000 × 300 = 최대 300k)

# UCDP type_of_violence → topic 매핑
_VIOLENCE_TOPIC = {
    1: "conflict",   # state-based
    2: "conflict",   # non-state
    3: "terror",     # one-sided (against civilians)
}

# UCDP 국가명 → ISO 2-letter 코드 매핑
# UCDP는 "Myanmar (Burma)", "DR Congo (Zaire)" 같은 특수 형태 사용
_UCDP_COUNTRY_TO_ISO: dict[str, str] = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "Angola": "AO",
    "Argentina": "AR", "Armenia": "AM", "Australia": "AU", "Azerbaijan": "AZ",
    "Bahrain": "BH",
    "Bangladesh": "BD", "Belarus": "BY", "Benin": "BJ", "Bolivia": "BO",
    "Bosnia-Herzegovina": "BA", "Brazil": "BR", "Burkina Faso": "BF",
    "Burundi": "BI", "Cambodia (Kampuchea)": "KH", "Cameroon": "CM",
    "Central African Republic": "CF", "Chad": "TD", "Chile": "CL",
    "China": "CN", "Colombia": "CO", "Comoros": "KM", "Congo": "CG",
    "Croatia": "HR", "Cuba": "CU", "Cyprus": "CY",
    "DR Congo (Zaire)": "CD", "Djibouti": "DJ",
    "Ecuador": "EC", "Egypt": "EG", "El Salvador": "SV",
    "Eritrea": "ER", "Ethiopia": "ET",
    "France": "FR",
    "Gabon": "GA", "Gambia": "GM", "Georgia": "GE", "Ghana": "GH",
    "Guatemala": "GT", "Guinea": "GN", "Guinea-Bissau": "GW",
    "Haiti": "HT", "Honduras": "HN", "Hungary": "HU",
    "India": "IN", "Indonesia": "ID", "Iran": "IR", "Iraq": "IQ",
    "Israel": "IL", "Ivory Coast": "CI",
    "Jamaica": "JM", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kosovo": "XK",
    "Kuwait": "KW", "Kyrgyzstan": "KG",
    "Laos": "LA", "Lebanon": "LB", "Lesotho": "LS",
    "Liberia": "LR", "Libya": "LY",
    "Macedonia, FYR": "MK", "Madagascar": "MG", "Malawi": "MW",
    "Malaysia": "MY", "Mali": "ML", "Mauritania": "MR",
    "Mexico": "MX", "Moldova": "MD", "Morocco": "MA",
    "Mozambique": "MZ", "Myanmar (Burma)": "MM",
    "Namibia": "NA", "Nepal": "NP", "Nicaragua": "NI",
    "Niger": "NE", "Nigeria": "NG", "North Korea": "KP",
    "Oman": "OM",
    "Pakistan": "PK", "Panama": "PA", "Papua New Guinea": "PG",
    "Paraguay": "PY", "Peru": "PE", "Philippines": "PH",
    "Romania": "RO", "Russia (Soviet Union)": "RU", "Rwanda": "RW",
    "Saudi Arabia": "SA", "Senegal": "SN", "Serbia": "RS",
    "Sierra Leone": "SL", "Somalia": "SO", "South Africa": "ZA",
    "South Korea": "KR", "South Sudan": "SS", "Spain": "ES",
    "Sri Lanka": "LK", "Sudan": "SD", "Suriname": "SR",
    "Syria": "SY",
    "Tajikistan": "TJ", "Tanzania": "TZ", "Thailand": "TH",
    "Togo": "TG", "Trinidad and Tobago": "TT", "Tunisia": "TN",
    "Turkey": "TR", "Turkmenistan": "TM",
    "Uganda": "UG", "Ukraine": "UA",
    "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States of America": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
    "Venezuela": "VE", "Vietnam": "VN",
    "Yemen (North Yemen)": "YE", "Zimbabwe": "ZW",
}


def _ucdp_country_to_iso(country_name: str) -> str:
    """UCDP 국가명 → ISO 2-letter 코드 변환."""
    if not country_name:
        return ""
    # 정확히 매칭
    code = _UCDP_COUNTRY_TO_ISO.get(country_name)
    if code:
        return code
    # 소문자 폴백
    lower = country_name.lower()
    for name, iso in _UCDP_COUNTRY_TO_ISO.items():
        if name.lower() == lower:
            return iso
    # 괄호 제거 후 재시도: "Cambodia (Kampuchea)" → "Cambodia"
    if "(" in country_name:
        base = country_name.split("(")[0].strip()
        for name, iso in _UCDP_COUNTRY_TO_ISO.items():
            if name.lower().startswith(base.lower()):
                return iso
    logger.warning("UCDP 국가 매핑 실패: %s", country_name)
    return ""


@dataclass
class UCDPCollectResult:
    display_name: str = "UCDP"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class UCDPCollector:
    TIMEOUT = 120  # 페이지당 최대 대기
    PAGE_SIZE = 1000  # API 최대 pagesize

    def _severity_from_fatalities(self, best: int, low: int, high: int) -> int:
        """사망자 수 기반 severity 계산."""
        ref = best if best > 0 else (low + high) // 2
        if ref == 0:
            return 30
        if ref <= 5:
            return 40
        if ref <= 25:
            return 55
        if ref <= 100:
            return 70
        if ref <= 500:
            return 85
        return 95

    async def _load_existing_ids(self, db: AsyncSession) -> set[str]:
        """기존 UCDP external_id를 한 번에 로드 (건별 SELECT 방지)."""
        result = await db.execute(
            select(RawEvent.external_id).where(
                RawEvent.source_type == "api",
                RawEvent.external_id.like("ucdp:%"),
            )
        )
        return {row[0] for row in result.fetchall()}

    async def collect(self, db: AsyncSession, redis=None) -> UCDPCollectResult:
        result = UCDPCollectResult()
        if not UCDP_ACCESS_TOKEN:
            result.errors.append("UCDP_ACCESS_TOKEN not set")
            return result

        # 기존 ID를 미리 로드 → 건별 SELECT 방지
        existing_ids = await self._load_existing_ids(db)
        logger.info("UCDP 기존 이벤트: %d건", len(existing_ids))

        headers = {"x-ucdp-access-token": UCDP_ACCESS_TOKEN}
        page = 1
        total_pages = 1

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                while page <= total_pages and page <= MAX_PAGES:
                    params = {
                        "pagesize": self.PAGE_SIZE,
                        "page": page,
                        "StartDate": START_DATE,
                    }
                    async with session.get(
                        UCDP_API_URL, headers=headers, params=params
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            result.errors.append(f"HTTP {resp.status}: {body[:200]}")
                            break
                        data = await resp.json(content_type=None)

                    total_pages = data.get("TotalPages", 1)
                    events = data.get("Result", [])
                    if not events:
                        break

                    batch = []
                    for ev in events:
                        try:
                            event_id = ev.get("id", ev.get("event_id_cnty", ""))
                            if not event_id:
                                result.skipped += 1
                                continue

                            external_id = f"ucdp:{event_id}"
                            if external_id in existing_ids:
                                result.skipped += 1
                                continue

                            # 데이터 추출
                            lat = float(ev.get("latitude", 0) or 0)
                            lon = float(ev.get("longitude", 0) or 0)
                            cc = _ucdp_country_to_iso(ev.get("country", ""))
                            violence_type = ev.get("type_of_violence", 1)
                            topic = _VIOLENCE_TOPIC.get(violence_type, "conflict")

                            best_fatalities = ev.get("best", 0) or 0
                            low_fatalities = ev.get("low", 0) or 0
                            high_fatalities = ev.get("high", 0) or 0
                            severity = self._severity_from_fatalities(
                                best_fatalities, low_fatalities, high_fatalities
                            )

                            date_str = ev.get("date_start", ev.get("date", ""))
                            try:
                                published_at = datetime.strptime(
                                    date_str[:10], "%Y-%m-%d"
                                ).replace(tzinfo=timezone.utc)
                            except ValueError:
                                published_at = datetime.now(timezone.utc)

                            side_a = ev.get("side_a", "") or ""
                            side_b = ev.get("side_b", "") or ""
                            where_desc = ev.get("where_description", "") or ev.get("adm_1", "") or ""
                            raw_text = f"UCDP: {side_a} vs {side_b} — {where_desc}"

                            raw_metadata = {
                                "title": raw_text[:512],
                                "published": published_at.isoformat(),
                                "structured_topic": topic,
                                "structured_severity": severity,
                                "structured_country": cc,
                                "structured_lat": lat,
                                "structured_lon": lon,
                                "source_tier": "A",
                                "ucdp_event_id": event_id,
                                "fatalities_best": best_fatalities,
                                "fatalities_low": low_fatalities,
                                "fatalities_high": high_fatalities,
                                "side_a": side_a,
                                "side_b": side_b,
                            }

                            raw_event = RawEvent(
                                source_channel_id=None,
                                source_type="api",
                                external_id=external_id,
                                raw_text=raw_text[:10000],
                                raw_metadata=raw_metadata,
                                lang="en",
                                collected_at=datetime.now(timezone.utc),
                            )
                            batch.append(raw_event)
                            existing_ids.add(external_id)
                            result.collected += 1
                        except Exception:
                            result.skipped += 1
                            continue

                    # 배치 insert
                    if batch:
                        db.add_all(batch)
                        result.raw_event_ids.extend(batch)

                    logger.info(
                        "UCDP 페이지 %d/%d 처리: +%d건 (누적 %d)",
                        page, min(total_pages, MAX_PAGES), len(batch), result.collected,
                    )
                    page += 1
                    if page <= total_pages:
                        await asyncio.sleep(0.5)

        except asyncio.TimeoutError:
            result.errors.append("API 타임아웃")
        except Exception as e:
            result.errors.append(f"API 오류: {e}")

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[UCDPCollectResult]:
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "UCDP 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("UCDP 수집 오류: %s", e)
            results.append(UCDPCollectResult(errors=[str(e)]))
        return results
