"""
USGS Earthquake API 수집기.
5분 주기로 USGS에서 M4.5+ 지진 목록을 폴링하고, M5.0 이상만 저장.

USGS GeoJSON Summary Feed는 인증 불요, rate-limit 관대.
구조화된 magnitude/depth/coordinates 데이터를 제공하므로
GPT 호출 없이 topic/severity/geo 매핑 가능 → 비용 절감.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# USGS M4.5+ 일간 피드 (GeoJSON)
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"

# 저장 기준: M4.5 이상 (5.0→4.5 완화, 데이터량 확보)
MIN_MAGNITUDE = 4.5

# 국가명 추출용 정규식: "123 km SSW of Someplace, Country" → "Country"
_PLACE_COUNTRY_RE = re.compile(r",\s*([A-Za-z][A-Za-z\s\-'.]+)$")


def _severity_from_magnitude(mag: float) -> int:
    """규모(magnitude) 기반 severity 계산 (구간별 선형 보간).

    M5.0 → 40, M6.0 → 55, M7.0 → 75, M8.0 → 95
    최솟값 40 (M5.0 미만은 수집 안 함), 최댓값 100.
    """
    # 보간 기준점
    breakpoints = [(5.0, 40), (6.0, 55), (7.0, 75), (8.0, 95)]

    if mag <= breakpoints[0][0]:
        return breakpoints[0][1]
    if mag >= breakpoints[-1][0]:
        # M8.0 이상: 같은 기울기(20/mag)로 외삽, cap 100
        severity = int(95 + (mag - 8.0) * 20)
        return min(100, severity)

    # 구간별 선형 보간
    for i in range(len(breakpoints) - 1):
        m0, s0 = breakpoints[i]
        m1, s1 = breakpoints[i + 1]
        if m0 <= mag <= m1:
            ratio = (mag - m0) / (m1 - m0)
            return int(s0 + ratio * (s1 - s0))

    return 40


def _extract_country(place: str) -> str:
    """properties.place에서 국가명 추출 시도.

    USGS place 형식: "123 km SSW of Someplace, Country"
    마지막 콤마 뒤의 텍스트가 국가명인 경우가 많음.
    추출 실패 시 빈 문자열 반환 (역지오코딩 안 함).
    """
    if not place:
        return ""
    match = _PLACE_COUNTRY_RE.search(place.strip())
    if match:
        return match.group(1).strip()
    return ""


@dataclass
class USGSEarthquakeCollectResult:
    display_name: str = "USGS Earthquake"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class USGSEarthquakeCollector:
    """USGS Earthquake GeoJSON Feed 수집기."""

    TIMEOUT = 30  # seconds

    async def collect(
        self,
        db: AsyncSession,
        redis=None,
    ) -> USGSEarthquakeCollectResult:
        """USGS 피드에서 M5.0+ 지진 이벤트 수집."""
        result = USGSEarthquakeCollectResult()

        # API 호출
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                async with session.get(USGS_FEED_URL) as resp:
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

        features = data.get("features", [])
        if not features:
            return result

        for feature in features:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [0, 0, 0])

            # magnitude 필터: M5.0 미만 스킵
            mag = props.get("mag")
            if mag is None or mag < MIN_MAGNITUDE:
                result.skipped += 1
                continue

            # external_id 결정
            # properties.ids는 ",us7000xxxx," 형태로 여러 ID 포함 가능
            # feature.id가 더 안정적 (예: "us7000xxxx")
            feature_id = feature.get("id", "")
            if not feature_id:
                ids_str = props.get("ids", "")
                feature_id = ids_str.strip(",").split(",")[0] if ids_str else ""
            if not feature_id:
                result.skipped += 1
                continue

            external_id = f"usgs:{feature_id}"

            # 중복 확인
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
            place = props.get("place", "")
            depth = coords[2] if len(coords) > 2 else 0
            lon = coords[0] if len(coords) > 0 else 0
            lat = coords[1] if len(coords) > 1 else 0
            tsunami = props.get("tsunami", 0)
            felt = props.get("felt")
            alert = props.get("alert")
            url = props.get("url", "")
            event_time = props.get("time")  # epoch ms

            # 국가명 추출 (역지오코딩 없이 place 파싱)
            country = _extract_country(place)

            # severity 계산
            severity = _severity_from_magnitude(mag)

            # published_at: USGS epoch ms → datetime
            published_at = None
            if event_time:
                try:
                    published_at = datetime.fromtimestamp(
                        event_time / 1000, tz=timezone.utc
                    )
                except (OSError, ValueError):
                    pass

            collected_at = datetime.now(timezone.utc)
            raw_text = f"M{mag} earthquake - {place}"

            raw_metadata = {
                "title": raw_text[:512],
                "link": url,
                "magnitude": mag,
                "depth": depth,
                "tsunami": tsunami,
                "felt": felt,
                "alert": alert,
                "place": place,
                "time": event_time,
                "url": url,
                "published": published_at.isoformat() if published_at else collected_at.isoformat(),
                "time_source": "usgs_origin_time" if published_at else "collected_at",
                # 구조화 데이터 (normalizer에서 GPT 스킵용)
                "structured_topic": "disaster",
                "structured_severity": severity,
                "structured_country": country,
                "structured_lat": lat,
                "structured_lon": lon,
            }

            raw_event = RawEvent(
                source_channel_id=None,  # SourceChannel 불요 (고정 피드)
                source_type="api",
                external_id=external_id,
                raw_text=raw_text[:10000],
                raw_metadata=raw_metadata,
                lang="en",
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(
        self, db: AsyncSession, redis=None
    ) -> list[USGSEarthquakeCollectResult]:
        """USGS 지진 데이터 수집 (단일 피드).

        다른 수집기와 인터페이스 통일을 위해 collect_all → list[Result] 형태.
        USGS는 SourceChannel 없이 고정 URL 사용.
        """
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "USGS 지진 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected, result.skipped, result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("USGS 지진 수집 오류: %s", e)
            results.append(USGSEarthquakeCollectResult(errors=[str(e)]))

        return results
