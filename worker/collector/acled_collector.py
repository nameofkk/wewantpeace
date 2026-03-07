"""
ACLED REST API 수집기.
주간 배치로 ACLED(Armed Conflict Location & Event Data)에서 분쟁 이벤트 수집.

ACLED는 완전 구조화된 데이터 (event_type, fatalities, geo)를 제공하므로
GPT 호출 없이 topic/severity/geo 직접 매핑 → 비용 절감.
"""
import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# ACLED event_type → wewantpeace topic 매핑
_EVENT_TYPE_TO_TOPIC: dict[str, str] = {
    "Battles": "conflict",
    "Violence against civilians": "conflict",
    "Explosions/Remote violence": "conflict",
    "Protests": "protest",
    "Riots": "protest",
    "Strategic developments": "diplomacy",
}

# ACLED event_type → severity 기본값
_EVENT_TYPE_SEVERITY: dict[str, int] = {
    "Battles": 65,
    "Violence against civilians": 70,
    "Explosions/Remote violence": 70,
    "Protests": 35,
    "Riots": 45,
    "Strategic developments": 30,
}


@dataclass
class ACLEDCollectResult:
    display_name: str = "ACLED"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class ACLEDCollector:
    """ACLED REST API 수집기."""

    TIMEOUT = 60  # ACLED 응답이 느릴 수 있음

    def _calc_severity(self, event_type: str, fatalities: int) -> int:
        """ACLED event_type + fatalities → severity."""
        base = _EVENT_TYPE_SEVERITY.get(event_type, 40)
        # 사망자 수에 따른 severity 상승
        if fatalities >= 100:
            base = min(100, base + 25)
        elif fatalities >= 10:
            base = min(100, base + 15)
        elif fatalities >= 1:
            base = min(100, base + 5)
        return base

    async def collect(
        self,
        source: SourceChannel,
        db: AsyncSession,
        redis=None,
    ) -> ACLEDCollectResult:
        """ACLED API에서 최근 1주일 이벤트 수집."""
        result = ACLEDCollectResult(display_name=source.display_name)

        api_endpoint = source.api_endpoint
        if not api_endpoint:
            result.errors.append("api_endpoint 없음")
            return result

        # ACLED API 키 (환경변수)
        acled_key = os.environ.get("ACLED_API_KEY", "")
        acled_email = os.environ.get("ACLED_EMAIL", "")

        # 최근 7일 이벤트만 조회
        since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        api_params = source.api_params or {}
        params = {
            **api_params,
            "event_date": since_date,
            "key": acled_key,
            "email": acled_email,
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as session:
                async with session.get(api_endpoint, params=params) as resp:
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

        events = data.get("data", [])
        if not events:
            return result

        for event in events:
            event_id = event.get("event_id_cnty", "")
            if not event_id:
                result.skipped += 1
                continue

            # 중복 확인
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "api",
                    RawEvent.external_id == f"acled:{event_id}",
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            event_type = event.get("event_type", "")
            sub_event_type = event.get("sub_event_type", "")
            notes = event.get("notes", "")
            country = event.get("country", "")
            admin1 = event.get("admin1", "")
            actor1 = event.get("actor1", "")
            fatalities = int(event.get("fatalities", 0) or 0)
            lat = float(event.get("latitude", 0) or 0)
            lon = float(event.get("longitude", 0) or 0)

            topic = _EVENT_TYPE_TO_TOPIC.get(event_type, "conflict")
            severity = self._calc_severity(event_type, fatalities)

            # 텍스트 구성: ACLED notes를 본문으로 사용
            title = f"{event_type}: {sub_event_type} in {admin1}, {country}"
            if actor1:
                title = f"{actor1} — {title}"
            text = notes if notes else title

            # event_date 파싱
            event_date_str = event.get("event_date", "")
            published_at = None
            if event_date_str:
                try:
                    published_at = datetime.strptime(
                        event_date_str[:10], "%Y-%m-%d"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            collected_at = datetime.now(timezone.utc)
            raw_metadata = {
                "title": title[:512],
                "link": f"https://acleddata.com/data-export-tool/",
                "event_type": event_type,
                "sub_event_type": sub_event_type,
                "actor1": actor1,
                "country": country,
                "admin1": admin1,
                "fatalities": fatalities,
                "lat": lat,
                "lon": lon,
                "source": event.get("source", ""),
                "published": published_at.isoformat() if published_at else collected_at.isoformat(),
                "time_source": "acled_event_date" if published_at else "collected_at",
                # 구조화 데이터 (normalizer에서 GPT 스킵용)
                "structured_topic": topic,
                "structured_severity": severity,
                "structured_country": country,
                "structured_lat": lat,
                "structured_lon": lon,
            }

            raw_event = RawEvent(
                source_channel_id=source.id,
                source_type="api",
                external_id=f"acled:{event_id}",
                raw_text=text[:10000],
                raw_metadata=raw_metadata,
                lang="en",
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[ACLEDCollectResult]:
        """모든 활성 ACLED 소스 수집."""
        stmt = select(SourceChannel).where(
            SourceChannel.is_active == True,
            SourceChannel.source_type == "api",
            SourceChannel.display_name.ilike("%acled%"),
        )
        channels_result = await db.execute(stmt)
        channels = list(channels_result.scalars().all())

        results = []
        for ch in channels:
            try:
                result = await self.collect(ch, db, redis=redis)
                logger.info(
                    "ACLED 수집 완료: %s (collected=%d, skipped=%d, errors=%s)",
                    ch.display_name, result.collected, result.skipped, result.errors,
                )
                results.append(result)
            except Exception as e:
                logger.error("ACLED 수집 오류: %s", e)
                results.append(ACLEDCollectResult(errors=[str(e)]))

        return results
