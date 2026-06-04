"""
ACLED REST API 수집기.
주간 배치로 ACLED(Armed Conflict Location & Event Data)에서 분쟁 이벤트 수집.

ACLED는 완전 구조화된 데이터 (event_type, fatalities, geo)를 제공하므로
GPT 호출 없이 topic/severity/geo 직접 매핑 → 비용 절감.

인증: 2025년부터 API 키 폐지 → OAuth 토큰 방식.
  - POST https://acleddata.com/oauth/token (email+password → Bearer 토큰)
  - 토큰 유효: 24시간, refresh_token: 14일
  - Redis에 토큰 캐싱하여 매 수집마다 재인증 방지
"""
import asyncio
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

# OAuth 토큰 Redis 키
_REDIS_TOKEN_KEY = "acled:oauth:access_token"
_REDIS_REFRESH_KEY = "acled:oauth:refresh_token"


@dataclass
class ACLEDCollectResult:
    display_name: str = "ACLED"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


class ACLEDCollector:
    """ACLED REST API 수집기 (OAuth 토큰 인증)."""

    TIMEOUT = 60
    OAUTH_URL = "https://acleddata.com/oauth/token"
    API_BASE = "https://acleddata.com/api/acled/read"

    def _calc_severity(self, event_type: str, fatalities: int) -> int:
        """ACLED event_type + fatalities → severity."""
        base = _EVENT_TYPE_SEVERITY.get(event_type, 40)
        if fatalities >= 100:
            base = min(100, base + 25)
        elif fatalities >= 10:
            base = min(100, base + 15)
        elif fatalities >= 1:
            base = min(100, base + 5)
        return base

    async def _get_access_token(self, redis=None) -> str | None:
        """OAuth 토큰 획득. Redis 캐싱 → refresh → 재인증 순."""
        # 1. Redis 캐시 확인
        if redis:
            cached = await redis.get(_REDIS_TOKEN_KEY)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached

        acled_email = os.environ.get("ACLED_EMAIL", "")
        acled_password = os.environ.get("ACLED_PASSWORD", "")
        if not acled_email or not acled_password:
            logger.warning("ACLED_EMAIL 또는 ACLED_PASSWORD 환경변수 없음")
            return None

        # 2. refresh_token으로 갱신 시도
        if redis:
            refresh = await redis.get(_REDIS_REFRESH_KEY)
            if refresh:
                refresh_str = refresh.decode() if isinstance(refresh, bytes) else refresh
                token = await self._refresh_token(refresh_str)
                if token:
                    await self._cache_tokens(redis, token)
                    return token["access_token"]

        # 3. 신규 인증
        token = await self._authenticate(acled_email, acled_password)
        if token and redis:
            await self._cache_tokens(redis, token)
        return token["access_token"] if token else None

    async def _authenticate(self, email: str, password: str) -> dict | None:
        """이메일+비밀번호로 OAuth 토큰 발급."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    self.OAUTH_URL,
                    data={
                        "username": email,
                        "password": password,
                        "grant_type": "password",
                        "client_id": "acled",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as resp:
                    if resp.status != 200:
                        logger.error("ACLED OAuth 인증 실패: HTTP %d", resp.status)
                        return None
                    data = await resp.json(content_type=None)
                    if "access_token" not in data:
                        logger.error("ACLED OAuth 응답에 access_token 없음: %s", data)
                        return None
                    logger.info("ACLED OAuth 인증 성공 (expires_in=%s)", data.get("expires_in"))
                    return data
        except Exception as e:
            logger.error("ACLED OAuth 인증 오류: %s", e)
            return None

    async def _refresh_token(self, refresh_token: str) -> dict | None:
        """refresh_token으로 access_token 갱신."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    self.OAUTH_URL,
                    data={
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                        "client_id": "acled",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning("ACLED refresh_token 갱신 실패: HTTP %d", resp.status)
                        return None
                    data = await resp.json(content_type=None)
                    if "access_token" in data:
                        logger.info("ACLED 토큰 갱신 성공")
                        return data
                    return None
        except Exception as e:
            logger.warning("ACLED refresh_token 오류: %s", e)
            return None

    async def _cache_tokens(self, redis, token_data: dict):
        """Redis에 토큰 캐싱."""
        expires_in = int(token_data.get("expires_in", 86400))
        # access_token: 만료 10분 전까지 캐싱
        await redis.setex(_REDIS_TOKEN_KEY, max(60, expires_in - 600), token_data["access_token"])
        # refresh_token: 14일
        if token_data.get("refresh_token"):
            await redis.setex(_REDIS_REFRESH_KEY, 86400 * 13, token_data["refresh_token"])

    async def collect(
        self,
        source: SourceChannel,
        db: AsyncSession,
        redis=None,
    ) -> ACLEDCollectResult:
        """ACLED API에서 최근 1주일 이벤트 수집."""
        result = ACLEDCollectResult(display_name=source.display_name)

        # OAuth 토큰 획득
        access_token = await self._get_access_token(redis=redis)
        if not access_token:
            result.errors.append("ACLED OAuth 토큰 획득 실패 (ACLED_EMAIL/ACLED_PASSWORD 환경변수 확인)")
            return result

        # 최근 7일 이벤트만 조회
        since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        params = {
            "limit": "200",
            "event_date": since_date,
            "event_date_where": ">=",
        }

        # Exponential backoff 재시도 (5s, 10s, 20s) — 401(토큰 만료)은 즉시 반환
        MAX_RETRIES = 3
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as session:
                    async with session.get(
                        self.API_BASE,
                        params=params,
                        headers={"Authorization": f"Bearer {access_token}"},
                    ) as resp:
                        if resp.status == 401:
                            # 토큰 만료 → 캐시 삭제 후 재인증 (재시도 무의미)
                            if redis:
                                await redis.delete(_REDIS_TOKEN_KEY)
                            result.errors.append("ACLED 토큰 만료 (다음 사이클에서 재인증)")
                            return result
                        if resp.status != 200:
                            raise aiohttp.ClientResponseError(
                                resp.request_info, resp.history,
                                status=resp.status, message=f"HTTP {resp.status}",
                            )
                        data = await resp.json(content_type=None)
                break  # 성공 시 루프 탈출
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s
                    logger.warning("ACLED fetch 재시도 %d/%d (%ds 후): %s", attempt + 1, MAX_RETRIES, wait, e)
                    await asyncio.sleep(wait)
                else:
                    logger.error("ACLED fetch 실패 (%d회 재시도 후): %s", MAX_RETRIES, e)
                    result.errors.append(f"API 오류 ({MAX_RETRIES}회 재시도 실패): {e}")
                    return result

        if data is None:
            result.errors.append("API 응답 없음")
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

            title = f"{event_type}: {sub_event_type} in {admin1}, {country}"
            if actor1:
                title = f"{actor1} — {title}"
            text = notes if notes else title

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
                "link": "https://acleddata.com/data-export-tool/",
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
