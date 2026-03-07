"""
GDELT DOC API 수집기.
15분 주기로 GDELT 2.0 DOC API에서 분쟁/시위/외교 관련 이벤트 수집.

GDELT는 구조화된 tone, theme, geo 데이터를 제공하므로
GPT 호출 없이 topic/severity/geo 매핑이 가능 → 비용 절감.
"""
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# GDELT theme → wewantpeace topic 매핑
_THEME_TO_TOPIC: dict[str, str] = {
    "CONFLICT": "conflict",
    "KILL": "conflict",
    "ARMED_CONFLICT": "conflict",
    "MILITARY": "conflict",
    "PROTEST": "protest",
    "TERROR": "terror",
    "COUP": "coup",
    "SANCTIONS": "sanctions",
    "CYBER_ATTACK": "cyber",
    "DIPLOMACY": "diplomacy",
    "MARITIME": "maritime",
    "NATURAL_DISASTER": "disaster",
    "HEALTH": "health",
    "EPIDEMIC": "health",
}

# GDELT tone → severity 기본 매핑 (tone 범위: -100 ~ +100)
# 부정적 tone이 클수록 severity 높음
_TONE_TO_SEVERITY_BASE = 50


@dataclass
class GDELTCollectResult:
    display_name: str = "GDELT"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class GDELTCollector:
    """GDELT DOC API 수집기."""

    TIMEOUT = 30  # seconds

    def _map_topic(self, themes: list[str]) -> str:
        """GDELT themes → wewantpeace topic."""
        for theme in themes:
            theme_upper = theme.upper().replace(" ", "_")
            for key, topic in _THEME_TO_TOPIC.items():
                if key in theme_upper:
                    return topic
        return "unknown"

    def _calc_severity(self, tone: float, topic: str) -> int:
        """GDELT tone + topic → severity (0-100)."""
        from worker.processor.normalizer import TOPIC_BASE_SEVERITY
        base = TOPIC_BASE_SEVERITY.get(topic, 40)
        # tone은 -100 ~ +100, 부정적일수록 severity 상승
        tone_delta = max(-20, min(20, int(-tone / 5)))
        return max(10, min(100, base + tone_delta))

    async def collect(
        self,
        source: SourceChannel,
        db: AsyncSession,
        redis=None,
    ) -> GDELTCollectResult:
        """GDELT DOC API에서 최신 기사 수집."""
        result = GDELTCollectResult(display_name=source.display_name)

        api_endpoint = source.api_endpoint
        api_params = source.api_params or {}
        if not api_endpoint:
            result.errors.append("api_endpoint 없음")
            return result

        # 분쟁/시위 관련 쿼리 — GDELT는 query 파라미터 필수
        params = {
            **api_params,
            "query": "conflict OR protest OR military OR attack OR sanctions",
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

        articles = data.get("articles", [])
        if not articles:
            return result

        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "")
            if not title or not url:
                result.skipped += 1
                continue

            # external_id: URL 해시 (안정적)
            ext_id = hashlib.md5(url.encode()).hexdigest()

            # 중복 확인
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "api",
                    RawEvent.external_id == f"gdelt:{ext_id}",
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            # GDELT 구조화 데이터 추출
            tone = article.get("tone", 0.0)
            if isinstance(tone, str):
                try:
                    tone = float(tone.split(",")[0])
                except (ValueError, IndexError):
                    tone = 0.0

            themes = []
            if article.get("themes"):
                if isinstance(article["themes"], str):
                    themes = article["themes"].split(";")
                elif isinstance(article["themes"], list):
                    themes = article["themes"]

            topic = self._map_topic(themes)
            severity = self._calc_severity(tone, topic)

            # geo 추출
            source_country = article.get("sourcecountry", "")
            domain = article.get("domain", "")

            # seendate 파싱 (YYYYMMDDTHHmmSS 형식)
            seen_date_str = article.get("seendate", "")
            published_at = None
            if seen_date_str:
                try:
                    published_at = datetime.strptime(
                        seen_date_str[:15], "%Y%m%dT%H%M%S"
                    ).replace(tzinfo=timezone.utc)
                except (ValueError, IndexError):
                    pass

            collected_at = datetime.now(timezone.utc)
            raw_metadata = {
                "title": title[:512],
                "link": url,
                "source_name": article.get("socialimage", ""),
                "domain": domain,
                "source_country": source_country,
                "tone": tone,
                "themes": themes[:10],
                "published": published_at.isoformat() if published_at else collected_at.isoformat(),
                "time_source": "gdelt_seendate" if published_at else "collected_at",
                # 구조화 데이터 (normalizer에서 GPT 스킵용)
                "structured_topic": topic,
                "structured_severity": severity,
                "image_url": article.get("socialimage", ""),
            }

            raw_event = RawEvent(
                source_channel_id=source.id,
                source_type="api",
                external_id=f"gdelt:{ext_id}",
                raw_text=title[:10000],
                raw_metadata=raw_metadata,
                lang=article.get("language", "en"),
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[GDELTCollectResult]:
        """모든 활성 GDELT 소스 수집."""
        stmt = select(SourceChannel).where(
            SourceChannel.is_active == True,
            SourceChannel.source_type == "api",
            SourceChannel.display_name.ilike("%gdelt%"),
        )
        channels_result = await db.execute(stmt)
        channels = list(channels_result.scalars().all())

        results = []
        for ch in channels:
            try:
                result = await self.collect(ch, db, redis=redis)
                logger.info(
                    "GDELT 수집 완료: %s (collected=%d, skipped=%d, errors=%s)",
                    ch.display_name, result.collected, result.skipped, result.errors,
                )
                results.append(result)
            except Exception as e:
                logger.error("GDELT 수집 오류: %s", e)
                results.append(GDELTCollectResult(errors=[str(e)]))

        return results
