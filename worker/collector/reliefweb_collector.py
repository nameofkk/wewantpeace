"""
ReliefWeb API 수집기.
30분 주기로 UN OCHA의 ReliefWeb 보고서에서 분쟁/재난/보건 관련 보고서 수집.

ReliefWeb은 자연재해, 보건 위기, 인도적 위기 보고서를 제공.
GPT-4o-mini로 정규화 (제목+본문이 비구조화 텍스트이므로).
"""
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)


@dataclass
class ReliefWebCollectResult:
    display_name: str = "ReliefWeb"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class ReliefWebCollector:
    """ReliefWeb API v1 수집기."""

    TIMEOUT = 30

    async def collect(
        self,
        source: SourceChannel,
        db: AsyncSession,
        redis=None,
    ) -> ReliefWebCollectResult:
        """ReliefWeb API에서 최신 보고서 수집."""
        result = ReliefWebCollectResult(display_name=source.display_name)

        api_endpoint = source.api_endpoint
        if not api_endpoint:
            result.errors.append("api_endpoint 없음")
            return result

        api_params = source.api_params or {}
        params = {**api_params}

        # v2 API 필수: appname 파라미터 (2025-11 이후 필수)
        if "appname" not in params:
            params["appname"] = "wewantpeace"

        # v1 API가 410 반환 시 v2로 자동 전환
        endpoints_to_try = [api_endpoint]
        if "/v1/" in api_endpoint:
            endpoints_to_try.append(api_endpoint.replace("/v1/", "/v2/"))

        data = None
        for ep in endpoints_to_try:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as session:
                    async with session.get(ep, params=params) as resp:
                        if resp.status in (410, 403) and ep != endpoints_to_try[-1]:
                            logger.warning("ReliefWeb API %s 반환 %d, v2로 전환 시도", ep, resp.status)
                            continue
                        if resp.status != 200:
                            result.errors.append(f"HTTP {resp.status}")
                            return result
                        data = await resp.json(content_type=None)
                        if ep != api_endpoint:
                            logger.info("ReliefWeb API v2 전환 성공: %s", ep)
                break
            except asyncio.TimeoutError:
                result.errors.append("API 타임아웃")
                return result
            except Exception as e:
                result.errors.append(f"API 오류: {e}")
                return result

        if data is None:
            result.errors.append("API 응답 없음 (v1/v2 모두 실패)")
            return result

        reports = data.get("data", [])
        if not reports:
            return result

        for report in reports:
            report_id = str(report.get("id", ""))
            if not report_id:
                result.skipped += 1
                continue

            # 중복 확인
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "api",
                    RawEvent.external_id == f"reliefweb:{report_id}",
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            fields = report.get("fields", {})
            title = fields.get("title", "")
            if not title:
                result.skipped += 1
                continue

            # 본문 추출 (HTML을 평문으로 — 간단한 태그 제거)
            body_html = fields.get("body", "")
            import re
            body = re.sub(r"<[^>]+>", " ", body_html)
            body = re.sub(r"\s+", " ", body).strip()[:5000]

            text = f"{title}\n\n{body}" if body else title

            # 날짜
            date_created = fields.get("date", {}).get("created", "")
            published_at = None
            if date_created:
                try:
                    published_at = datetime.fromisoformat(
                        date_created.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            # 국가 정보
            countries = fields.get("country", [])
            country_names = [c.get("name", "") for c in countries if isinstance(c, dict)]

            # 재해 유형
            disaster_types = fields.get("disaster_type", [])
            disaster_names = [d.get("name", "") for d in disaster_types if isinstance(d, dict)]

            # 출처
            sources = fields.get("source", [])
            source_names = [s.get("name", "") for s in sources if isinstance(s, dict)]

            # URL
            url = fields.get("url", f"https://reliefweb.int/node/{report_id}")

            # 이미지
            image_url = ""
            if fields.get("file"):
                files = fields["file"]
                if isinstance(files, list) and files:
                    image_url = files[0].get("url", "")

            collected_at = datetime.now(timezone.utc)
            raw_metadata = {
                "title": title[:512],
                "link": url,
                "countries": country_names,
                "disaster_types": disaster_names,
                "sources": source_names,
                "published": published_at.isoformat() if published_at else collected_at.isoformat(),
                "time_source": "reliefweb_date" if published_at else "collected_at",
            }
            if image_url:
                raw_metadata["image_url"] = image_url

            raw_event = RawEvent(
                source_channel_id=source.id,
                source_type="api",
                external_id=f"reliefweb:{report_id}",
                raw_text=text[:10000],
                raw_metadata=raw_metadata,
                lang="en",
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[ReliefWebCollectResult]:
        """모든 활성 ReliefWeb 소스 수집."""
        stmt = select(SourceChannel).where(
            SourceChannel.is_active == True,
            SourceChannel.source_type == "api",
            SourceChannel.display_name.ilike("%reliefweb%"),
        )
        channels_result = await db.execute(stmt)
        channels = list(channels_result.scalars().all())

        results = []
        for ch in channels:
            try:
                result = await self.collect(ch, db, redis=redis)
                logger.info(
                    "ReliefWeb 수집 완료: %s (collected=%d, skipped=%d, errors=%s)",
                    ch.display_name, result.collected, result.skipped, result.errors,
                )
                results.append(result)
            except Exception as e:
                logger.error("ReliefWeb 수집 오류: %s", e)
                results.append(ReliefWebCollectResult(errors=[str(e)]))

        return results
