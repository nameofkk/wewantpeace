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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

UCDP_ACCESS_TOKEN = os.environ.get("UCDP_ACCESS_TOKEN", "")
UCDP_API_URL = "https://ucdpapi.pcr.uu.se/api/gedevents/v25.1"

# UCDP type_of_violence → topic 매핑
_VIOLENCE_TOPIC = {
    1: "conflict",   # state-based
    2: "conflict",   # non-state
    3: "terror",     # one-sided (against civilians)
}


@dataclass
class UCDPCollectResult:
    display_name: str = "UCDP"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class UCDPCollector:
    TIMEOUT = 60
    PAGE_SIZE = 100

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

    async def collect(self, db: AsyncSession, redis=None) -> UCDPCollectResult:
        result = UCDPCollectResult()
        if not UCDP_ACCESS_TOKEN:
            result.errors.append("UCDP_ACCESS_TOKEN not set")
            return result

        headers = {"x-ucdp-access-token": UCDP_ACCESS_TOKEN}
        page = 1
        total_pages = 1

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                while page <= total_pages:
                    params = {
                        "pagesize": self.PAGE_SIZE,
                        "page": page,
                    }
                    async with session.get(
                        UCDP_API_URL, headers=headers, params=params
                    ) as resp:
                        if resp.status != 200:
                            result.errors.append(f"HTTP {resp.status}")
                            break
                        data = await resp.json(content_type=None)

                    total_pages = data.get("TotalPages", 1)
                    events = data.get("Result", [])
                    if not events:
                        break

                    for ev in events:
                        try:
                            event_id = ev.get("id", ev.get("event_id_cnty", ""))
                            if not event_id:
                                result.skipped += 1
                                continue

                            external_id = f"ucdp:{event_id}"

                            existing = await db.execute(
                                select(RawEvent).where(
                                    RawEvent.source_type == "api",
                                    RawEvent.external_id == external_id,
                                )
                            )
                            if existing.scalar_one_or_none():
                                result.skipped += 1
                                continue

                            # 데이터 추출
                            lat = float(ev.get("latitude", 0))
                            lon = float(ev.get("longitude", 0))
                            cc = ev.get("country_code", ev.get("country", ""))[:4]
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

                            side_a = ev.get("side_a", "")
                            side_b = ev.get("side_b", "")
                            where_desc = ev.get("where_description", ev.get("adm_1", ""))
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
                            db.add(raw_event)
                            result.raw_event_ids.append(raw_event)
                            result.collected += 1
                        except Exception:
                            result.skipped += 1
                            continue

                    page += 1
                    if page <= total_pages:
                        await asyncio.sleep(1)

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
