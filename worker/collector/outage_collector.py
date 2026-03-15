"""
IODA 인터넷 단절 수집기.
15분 주기로 CAIDA IODA에서 분쟁지역 인터넷 단절 이벤트를 수집.
signal_points 테이블에 직접 저장.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# IODA API (인증 불필요)
IODA_EVENTS_URL = "https://ioda.caida.org/ioda/data/events"

# 분쟁 16개국
MONITORED_COUNTRIES = [
    "UA", "PS", "SY", "YE", "MM", "SD", "SO", "AF",
    "IR", "IQ", "RU", "BY", "ET", "LY", "CD", "ML",
]

# 국가 중심 좌표 (normalizer.py COUNTRY_CENTERS 재사용 패턴)
COUNTRY_CENTERS: dict[str, tuple[float, float]] = {
    "UA": (48.38, 31.17), "PS": (31.95, 35.23), "SY": (34.80, 38.99),
    "YE": (15.55, 48.52), "MM": (21.91, 95.96), "SD": (12.86, 30.22),
    "SO": (5.15, 46.20), "AF": (33.94, 67.71), "IR": (32.43, 53.69),
    "IQ": (33.22, 43.68), "RU": (61.52, 105.32), "BY": (53.71, 27.95),
    "ET": (9.15, 40.49), "LY": (26.34, 17.23), "CD": (-4.04, 21.76),
    "ML": (17.57, -4.00),
}


@dataclass
class OutageCollectResult:
    display_name: str = "IODA Outage"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class OutageCollector:
    """CAIDA IODA 인터넷 단절 수집기."""

    TIMEOUT = 30

    async def collect(self, db: AsyncSession, redis=None) -> OutageCollectResult:
        """IODA API에서 분쟁지역 인터넷 단절 이벤트 수집."""
        result = OutageCollectResult()
        from backend.app.models.signal_point import SignalPoint

        now = datetime.now(timezone.utc)
        # 최근 1시간 이벤트 조회
        since = int((now - timedelta(hours=1)).timestamp())
        until = int(now.timestamp())

        try:
            params = {
                "from": since,
                "until": until,
            }
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                async with session.get(IODA_EVENTS_URL, params=params) as resp:
                    if resp.status != 200:
                        result.errors.append(f"HTTP {resp.status}")
                        return result
                    data = await resp.json(content_type=None)
        except asyncio.TimeoutError:
            result.errors.append("API 타임아웃")
            return result
        except Exception as e:
            result.errors.append(f"API 오류: {e}")
            return result

        events = data if isinstance(data, list) else data.get("data", data.get("events", []))
        if not isinstance(events, list):
            return result

        for event in events:
            try:
                # IODA 이벤트 구조 파싱
                location = event.get("location", {})
                cc = ""
                if isinstance(location, dict):
                    cc = location.get("code", "").upper()
                elif isinstance(event.get("entity", {}), dict):
                    entity = event.get("entity", {})
                    cc = entity.get("code", "").upper()

                # country code 직접 제공되지 않으면 name에서 추출 시도
                if not cc or len(cc) != 2:
                    cc = event.get("country", event.get("cc", "")).upper()

                if cc not in MONITORED_COUNTRIES:
                    result.skipped += 1
                    continue

                # fraction: 정상 트래픽 대비 비율 (0=완전단절, 1=정상)
                fraction = event.get("fraction", event.get("score", 1.0))
                if fraction is None:
                    fraction = 1.0
                try:
                    fraction = float(fraction)
                except (ValueError, TypeError):
                    fraction = 1.0

                if fraction >= 0.5:
                    result.skipped += 1
                    continue

                intensity = round(1.0 - fraction, 3)

                # 타임스탬프
                ts = event.get("start", event.get("from", event.get("time")))
                if ts:
                    if isinstance(ts, (int, float)):
                        observed_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                    else:
                        observed_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                else:
                    observed_at = now

                # 5분 단위로 반올림
                rounded_ts = observed_at.replace(second=0, microsecond=0)
                rounded_ts = rounded_ts.replace(minute=(rounded_ts.minute // 5) * 5)

                datasource = event.get("datasource", event.get("type", "unknown"))
                external_id = f"ioda:{cc}:{datasource}:{int(rounded_ts.timestamp())}"

                # 중복 확인
                existing = await db.execute(
                    select(SignalPoint).where(SignalPoint.external_id == external_id)
                )
                if existing.scalar_one_or_none():
                    result.skipped += 1
                    continue

                center = COUNTRY_CENTERS.get(cc, (0.0, 0.0))

                sp = SignalPoint(
                    signal_type="ioda_outage",
                    external_id=external_id,
                    lat=center[0],
                    lon=center[1],
                    country_code=cc,
                    intensity=intensity,
                    raw_value=fraction,
                    confidence=0.7,
                    metadata={"datasource": datasource, "fraction": fraction},
                    observed_at=observed_at,
                    expires_at=observed_at + timedelta(hours=48),
                )
                db.add(sp)
                result.collected += 1
            except Exception:
                result.skipped += 1
                continue

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[OutageCollectResult]:
        """IODA 인터넷 단절 데이터 수집.

        다른 수집기와 인터페이스 통일을 위해 collect_all -> list[Result] 형태.
        """
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "IODA 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("IODA 수집 오류: %s", e)
            results.append(OutageCollectResult(errors=[str(e)]))
        return results
