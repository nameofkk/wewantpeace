"""
NASA FIRMS 위성 열점 수집기.
15분 주기로 MODIS/VIIRS 센서에서 화재/폭발 열점을 수집.
signal_points 테이블에 직접 저장 (GPT 정규화 불필요).
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

# NASA FIRMS MAP_KEY (무료 발급)
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")

# 센서별 API URL
FIRMS_CSV_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/world/2"

# 필터 기준
MIN_FRP = 10  # MW
MIN_CONFIDENCE_MODIS = 50  # %
VIIRS_NOMINAL = "nominal"


@dataclass
class FIRMSCollectResult:
    display_name: str = "NASA FIRMS"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class FIRMSCollector:
    """NASA FIRMS 위성 열점 수집기."""

    TIMEOUT = 60
    SENSORS = ["MODIS_NRT", "VIIRS_NOAA20_NRT"]

    async def collect(self, db: AsyncSession, redis=None) -> FIRMSCollectResult:
        """FIRMS API에서 화재/폭발 열점 수집."""
        result = FIRMSCollectResult()
        if not FIRMS_MAP_KEY:
            result.errors.append("FIRMS_MAP_KEY not set")
            return result

        from backend.app.models.signal_point import SignalPoint

        for source in self.SENSORS:
            url = FIRMS_CSV_URL.format(map_key=FIRMS_MAP_KEY, source=source)
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
                ) as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            result.errors.append(f"{source}: HTTP {resp.status}")
                            continue
                        text = await resp.text()
            except asyncio.TimeoutError:
                result.errors.append(f"{source}: 타임아웃")
                continue
            except Exception as e:
                result.errors.append(f"{source}: {e}")
                continue

            lines = text.strip().split("\n")
            if len(lines) < 2:
                continue

            header = lines[0].split(",")
            # CSV 컬럼 인덱스 매핑
            col_map = {h.strip(): i for i, h in enumerate(header)}

            for line in lines[1:]:
                try:
                    cols = line.split(",")
                    lat = float(cols[col_map.get("latitude", 0)])
                    lon = float(cols[col_map.get("longitude", 1)])

                    # confidence 필터
                    conf_raw = cols[col_map.get("confidence", -1)].strip() if "confidence" in col_map else "0"

                    if source.startswith("MODIS"):
                        try:
                            conf_val = int(conf_raw)
                        except ValueError:
                            result.skipped += 1
                            continue
                        if conf_val < MIN_CONFIDENCE_MODIS:
                            result.skipped += 1
                            continue
                        conf_multiplier = conf_val / 100.0
                    else:  # VIIRS
                        if conf_raw.lower() not in ("nominal", "high"):
                            result.skipped += 1
                            continue
                        conf_multiplier = 0.8 if conf_raw.lower() == "nominal" else 1.0

                    # FRP 필터
                    frp_str = cols[col_map.get("frp", -1)].strip() if "frp" in col_map else "0"
                    try:
                        frp = float(frp_str)
                    except ValueError:
                        frp = 0.0
                    if frp < MIN_FRP:
                        result.skipped += 1
                        continue

                    # intensity 정규화
                    intensity = min(1.0, frp / 500.0) * conf_multiplier

                    # acq_date, acq_time
                    acq_date = cols[col_map.get("acq_date", -1)].strip() if "acq_date" in col_map else ""
                    acq_time = cols[col_map.get("acq_time", -1)].strip() if "acq_time" in col_map else "0000"

                    # observed_at
                    try:
                        observed_at = datetime.strptime(
                            f"{acq_date} {acq_time}", "%Y-%m-%d %H%M"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        observed_at = datetime.now(timezone.utc)

                    external_id = f"firms:{source}:{acq_date}:{round(lat, 3)}:{round(lon, 3)}"

                    # 중복 확인
                    existing = await db.execute(
                        select(SignalPoint).where(SignalPoint.external_id == external_id)
                    )
                    if existing.scalar_one_or_none():
                        result.skipped += 1
                        continue

                    sp = SignalPoint(
                        signal_type="firms_hotspot",
                        external_id=external_id,
                        lat=lat,
                        lon=lon,
                        intensity=intensity,
                        raw_value=frp,
                        confidence=conf_multiplier,
                        extra_data={"source": source, "frp": frp, "confidence_raw": conf_raw},
                        observed_at=observed_at,
                        expires_at=observed_at + timedelta(hours=24),
                    )
                    db.add(sp)
                    result.collected += 1
                except (IndexError, ValueError):
                    result.skipped += 1
                    continue

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[FIRMSCollectResult]:
        """FIRMS 열점 데이터 수집 (센서 통합).

        다른 수집기와 인터페이스 통일을 위해 collect_all -> list[Result] 형태.
        """
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "FIRMS 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("FIRMS 수집 오류: %s", e)
            results.append(FIRMSCollectResult(errors=[str(e)]))
        return results
