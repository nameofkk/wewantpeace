"""
Cloudflare Radar 트래픽 이상 수집기.
30분 주기로 Cloudflare Radar API에서 트래픽 이상 감지.
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

CF_RADAR_TOKEN = os.environ.get("CF_RADAR_TOKEN", "")
CF_RADAR_URL = "https://api.cloudflare.com/client/v4/radar/traffic_anomalies/latest"

# 국가 중심 좌표
COUNTRY_CENTERS: dict[str, tuple[float, float]] = {
    "UA": (48.38, 31.17), "PS": (31.95, 35.23), "SY": (34.80, 38.99),
    "YE": (15.55, 48.52), "MM": (21.91, 95.96), "SD": (12.86, 30.22),
    "SO": (5.15, 46.20), "AF": (33.94, 67.71), "IR": (32.43, 53.69),
    "IQ": (33.22, 43.68), "RU": (61.52, 105.32), "BY": (53.71, 27.95),
    "ET": (9.15, 40.49), "LY": (26.34, 17.23), "CD": (-4.04, 21.76),
    "ML": (17.57, -4.00), "KP": (40.34, 127.51), "CN": (35.86, 104.20),
}


@dataclass
class CloudflareRadarCollectResult:
    display_name: str = "Cloudflare Radar"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class CloudflareRadarCollector:
    TIMEOUT = 30

    async def collect(self, db: AsyncSession, redis=None) -> CloudflareRadarCollectResult:
        result = CloudflareRadarCollectResult()
        if not CF_RADAR_TOKEN:
            result.errors.append("CF_RADAR_TOKEN not set")
            return result

        from backend.app.models.signal_point import SignalPoint

        headers = {
            "Authorization": f"Bearer {CF_RADAR_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                async with session.get(CF_RADAR_URL, headers=headers) as resp:
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

        anomalies = data.get("result", {}).get("trafficAnomalies", [])
        if not anomalies:
            return result

        for anomaly in anomalies:
            try:
                locations = anomaly.get("locations", [])
                start_time = anomaly.get("startDate", anomaly.get("startTime", ""))
                impact = anomaly.get("value", anomaly.get("estimatedImpact", 0.5))

                try:
                    intensity = float(impact)
                    intensity = max(0.0, min(1.0, intensity))
                except (ValueError, TypeError):
                    intensity = 0.5

                if start_time:
                    try:
                        observed_at = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    except ValueError:
                        observed_at = datetime.now(timezone.utc)
                else:
                    observed_at = datetime.now(timezone.utc)

                for loc in locations:
                    cc = loc.get("code", loc.get("locationCode", "")).upper()
                    if not cc or len(cc) != 2:
                        continue

                    external_id = f"cf:{cc}:{start_time}"

                    existing = await db.execute(
                        select(SignalPoint).where(SignalPoint.external_id == external_id)
                    )
                    if existing.scalar_one_or_none():
                        result.skipped += 1
                        continue

                    center = COUNTRY_CENTERS.get(cc, (0.0, 0.0))

                    sp = SignalPoint(
                        signal_type="cf_anomaly",
                        external_id=external_id,
                        lat=center[0],
                        lon=center[1],
                        country_code=cc,
                        intensity=intensity,
                        raw_value=intensity,
                        confidence=0.6,
                        extra_data={
                            "source": "cloudflare_radar",
                            "impact": impact,
                            "start_time": start_time,
                        },
                        observed_at=observed_at,
                        expires_at=observed_at + timedelta(hours=48),
                    )
                    db.add(sp)
                    result.collected += 1
            except Exception:
                result.skipped += 1
                continue

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[CloudflareRadarCollectResult]:
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "Cloudflare Radar 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("Cloudflare Radar 수집 오류: %s", e)
            results.append(CloudflareRadarCollectResult(errors=[str(e)]))
        return results
