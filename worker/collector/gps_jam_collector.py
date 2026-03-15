"""
GPS 교란 탐지 수집기.
15분 주기로 분쟁 지역 상공의 GPS 교란 징후를 수집.
ADS-B 데이터 기반 간접 추론 방식.
signal_points 테이블에 직접 저장.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ADS-B Exchange API (대안: OpenSky Network)
ADSB_API_KEY = os.environ.get("ADSB_API_KEY", "")
OPENSKY_URL = "https://opensky-network.org/api/states/all"

# 분쟁 지역 bbox: (min_lat, max_lat, min_lon, max_lon, name)
CONFLICT_ZONES: list[dict] = [
    {"name": "ukraine", "bbox": (44.0, 52.5, 22.0, 40.5), "cc": "UA", "center": (48.38, 31.17)},
    {"name": "israel_palestine", "bbox": (29.0, 33.5, 34.0, 36.0), "cc": "PS", "center": (31.95, 35.23)},
    {"name": "syria", "bbox": (32.0, 37.5, 35.5, 42.5), "cc": "SY", "center": (34.80, 38.99)},
    {"name": "yemen", "bbox": (12.0, 19.0, 42.0, 54.0), "cc": "YE", "center": (15.55, 48.52)},
    {"name": "iran", "bbox": (25.0, 40.0, 44.0, 63.5), "cc": "IR", "center": (32.43, 53.69)},
    {"name": "iraq", "bbox": (29.0, 37.5, 38.5, 49.0), "cc": "IQ", "center": (33.22, 43.68)},
    {"name": "libya", "bbox": (19.5, 33.5, 9.0, 25.5), "cc": "LY", "center": (26.34, 17.23)},
    {"name": "sudan", "bbox": (3.5, 22.0, 21.5, 39.0), "cc": "SD", "center": (12.86, 30.22)},
    {"name": "ethiopia", "bbox": (3.5, 15.0, 33.0, 48.0), "cc": "ET", "center": (9.15, 40.49)},
    {"name": "myanmar", "bbox": (9.5, 28.5, 92.0, 101.5), "cc": "MM", "center": (21.91, 95.96)},
]

# GPS 교란 판정 기준
LOW_ACCURACY_THRESHOLD = 6  # nac_p < 6
JAM_RATIO_THRESHOLD = 0.3   # 30% 초과


@dataclass
class GpsJamCollectResult:
    display_name: str = "GPS Jamming"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class GpsJamCollector:
    TIMEOUT = 45

    async def _check_zone(
        self, session: aiohttp.ClientSession, zone: dict
    ) -> dict | None:
        """단일 지역의 GPS 교란 여부를 OpenSky 데이터로 확인."""
        min_lat, max_lat, min_lon, max_lon = zone["bbox"]
        params = {
            "lamin": min_lat,
            "lamax": max_lat,
            "lomin": min_lon,
            "lomax": max_lon,
        }

        try:
            async with session.get(OPENSKY_URL, params=params) as resp:
                if resp.status == 429:
                    return None  # rate limit
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        except Exception:
            return None

        states = data.get("states", [])
        if not states or len(states) < 5:
            return None  # 충분한 항공기가 없음

        low_accuracy_count = 0
        total = len(states)

        for state in states:
            # OpenSky state vector: index 13 = position_source (0=ADS-B)
            # nac_p는 직접 제공되지 않으므로 position_source와 on_ground 기반 추론
            # 위치 정확도가 낮은 항공기 판별: vertical_rate, velocity가 None인 경우
            velocity = state[9] if len(state) > 9 else None
            vertical_rate = state[11] if len(state) > 11 else None
            on_ground = state[8] if len(state) > 8 else True
            lat = state[6] if len(state) > 6 else None
            lon = state[5] if len(state) > 5 else None

            if on_ground or lat is None or lon is None:
                total -= 1
                continue

            # GPS 교란 시 velocity/vertical_rate가 비정상적으로 None이 되는 패턴
            if velocity is None and vertical_rate is None:
                low_accuracy_count += 1

        if total < 3:
            return None

        ratio = low_accuracy_count / total
        if ratio < JAM_RATIO_THRESHOLD:
            return None

        return {
            "zone": zone,
            "ratio": round(ratio, 3),
            "total_aircraft": total,
            "low_accuracy": low_accuracy_count,
        }

    async def collect(self, db: AsyncSession, redis=None) -> GpsJamCollectResult:
        result = GpsJamCollectResult()
        from backend.app.models.signal_point import SignalPoint

        now = datetime.now(timezone.utc)
        rounded_ts = now.replace(second=0, microsecond=0)
        rounded_ts = rounded_ts.replace(minute=(rounded_ts.minute // 15) * 15)

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                # 순차적으로 확인 (OpenSky rate limit: 10 req/min for anonymous)
                for zone in CONFLICT_ZONES:
                    detection = await self._check_zone(session, zone)
                    if detection is None:
                        result.skipped += 1
                        continue

                    z = detection["zone"]
                    external_id = f"gps_jam:{z['cc']}:{int(rounded_ts.timestamp())}"

                    existing = await db.execute(
                        select(SignalPoint).where(SignalPoint.external_id == external_id)
                    )
                    if existing.scalar_one_or_none():
                        result.skipped += 1
                        continue

                    sp = SignalPoint(
                        signal_type="gps_jam",
                        external_id=external_id,
                        lat=z["center"][0],
                        lon=z["center"][1],
                        country_code=z["cc"],
                        intensity=min(1.0, detection["ratio"]),
                        raw_value=detection["ratio"],
                        confidence=0.5,
                        metadata={
                            "region": z["name"],
                            "aircraft_count": detection["total_aircraft"],
                            "low_accuracy_count": detection["low_accuracy"],
                            "ratio": detection["ratio"],
                        },
                        observed_at=now,
                        expires_at=now + timedelta(hours=12),
                    )
                    db.add(sp)
                    result.collected += 1

                    # rate limit 존중
                    await asyncio.sleep(6)

        except Exception as e:
            result.errors.append(f"수집 오류: {e}")

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[GpsJamCollectResult]:
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "GPS 교란 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("GPS 교란 수집 오류: %s", e)
            results.append(GpsJamCollectResult(errors=[str(e)]))
        return results
