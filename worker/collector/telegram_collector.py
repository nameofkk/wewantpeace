"""
Telegram Bot API getUpdates 방식 수집기.
화이트리스트(source_channels)에 등록된 채널의 포워드 메시지를 수집.

주의: Bot은 채널에 admin으로 추가되어야 메시지를 수신할 수 있음.
또는 Bot이 채널 멤버인 상태에서 forwardFrom 채널 메시지를 수집.
MVP-1에서는 getUpdates 폴링 방식 사용 (MTProto는 MVP-2에서 도입).
"""
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


@dataclass
class CollectResult:
    channel_id: int
    display_name: str
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)  # 저장된 raw_event ID 목록


class TelegramCollector:
    """Telegram Bot API를 통해 화이트리스트 채널 메시지 수집."""

    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or settings.telegram_bot_token
        self._last_update_id: int = 0

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}"

    async def get_updates(
        self,
        offset: int = 0,
        limit: int = 100,
        timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Telegram getUpdates API 호출."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN 미설정 - 수집 건너뜀")
            return []
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": offset, "limit": limit, "timeout": timeout},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
                else:
                    logger.error("Telegram API 오류: %s", data)
                    return []
            except httpx.HTTPError as e:
                # 토큰이 URL에 포함되므로 로그에서 마스킹 처리 (H-7)
                masked = str(e).replace(self.bot_token, "***TOKEN***") if self.bot_token else str(e)
                logger.error("Telegram HTTP 오류: %s", masked)
                return []

    def _parse_message(
        self,
        update: dict[str, Any],
        channel: SourceChannel,
    ) -> dict[str, Any] | None:
        """
        Telegram update dict → raw_event 데이터 dict.
        미디어 전용 메시지 또는 빈 텍스트는 None 반환.
        """
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            return None

        # 텍스트 추출 (caption 포함)
        text = msg.get("text") or msg.get("caption") or ""
        text = text.strip()
        if not text or len(text) < 10:
            return None

        # 메시지 ID → external_id
        message_id = msg.get("message_id")
        chat_id = msg.get("chat", {}).get("id", 0)
        external_id = f"{chat_id}_{message_id}"

        # 메타데이터 추출
        raw_metadata: dict[str, Any] = {
            "views": msg.get("views", 0),
            "forwards": msg.get("forwards", 0),
            "replies": msg.get("replies", {}).get("replies", 0),
            "date": msg.get("date"),
            "has_media": bool(
                msg.get("photo") or msg.get("video") or msg.get("document")
            ),
            "url": msg.get("web_page", {}).get("url") if msg.get("web_page") else None,
        }

        # 발송 시각
        ts = msg.get("date")
        event_time = (
            datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        )

        return {
            "source_channel_id": channel.id,
            "source_type": "telegram",
            "external_id": external_id,
            "raw_text": text,
            "raw_metadata": raw_metadata,
            "lang": None,  # Week 2 Normalizer에서 감지
            "collected_at": datetime.now(timezone.utc),
        }

    async def collect_channel(
        self,
        channel: SourceChannel,
        db: AsyncSession,
        updates: list[dict[str, Any]],
    ) -> CollectResult:
        """
        전달받은 updates에서 해당 채널(channel_id)의 메시지를 필터링하여 수집.
        """
        result = CollectResult(
            channel_id=channel.channel_id or 0,
            display_name=channel.display_name,
        )

        for update in updates:
            msg = update.get("message") or update.get("channel_post")
            if not msg:
                continue

            chat = msg.get("chat", {})
            chat_id = chat.get("id", 0)

            # 채널 ID 매칭 (채널은 음수 100으로 시작)
            if channel.channel_id and abs(chat_id) != abs(channel.channel_id):
                continue

            parsed = self._parse_message(update, channel)
            if parsed is None:
                result.skipped += 1
                continue

            # INSERT OR IGNORE (unique constraint)
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "telegram",
                    RawEvent.external_id == parsed["external_id"],
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            raw_event = RawEvent(**parsed)
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)  # flush 후 ID 확보용
            result.collected += 1

        # flush는 호출하지 않음 — tasks.py에서 일괄 commit 처리
        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[CollectResult]:
        """
        1. 활성 Telegram 채널 목록 조회
        2. getUpdates 한 번 호출 (last_update_id Redis에서 복원)
        3. 각 채널별로 메시지 필터링 및 저장
        """
        _REDIS_KEY = "telegram:last_update_id"

        # 활성 채널 조회
        stmt = select(SourceChannel).where(
            SourceChannel.is_active == True,
            SourceChannel.source_type == "telegram",
        )
        channels_result = await db.execute(stmt)
        channels: list[SourceChannel] = list(channels_result.scalars().all())

        if not channels:
            logger.info("활성 Telegram 채널 없음")
            return []

        # Redis에서 마지막 update_id 복원 (태스크 재시작 시 중복 방지)
        if redis is not None:
            try:
                saved_id = await redis.get(_REDIS_KEY)
                if saved_id:
                    self._last_update_id = int(saved_id)
            except Exception as e:
                logger.warning("Redis last_update_id 로드 실패: %s", e)

        # 업데이트 수집
        updates = await self.get_updates(offset=self._last_update_id + 1, limit=100)

        if updates:
            self._last_update_id = max(u["update_id"] for u in updates)
            # Redis에 저장 (영속성)
            if redis is not None:
                try:
                    await redis.set(_REDIS_KEY, str(self._last_update_id))
                except Exception as e:
                    logger.warning("Redis last_update_id 저장 실패: %s", e)

        # 채널별 처리
        results = []
        for channel in channels:
            try:
                result = await self.collect_channel(channel, db, updates)
                results.append(result)
                logger.info(
                    "Telegram 수집 완료: %s (collected=%d, skipped=%d)",
                    channel.display_name,
                    result.collected,
                    result.skipped,
                )
            except Exception as e:
                logger.error("채널 %s 수집 오류: %s", channel.display_name, e)
                results.append(
                    CollectResult(
                        channel_id=channel.channel_id or 0,
                        display_name=channel.display_name,
                        errors=[str(e)],
                    )
                )

        return results
