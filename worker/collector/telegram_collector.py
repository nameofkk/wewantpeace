"""
Telegram MTProto(Telethon) 기반 공개 채널 수집기.
Bot token + api_id/api_hash 조합으로 Telethon 클라이언트를 만들어
공개 채널의 메시지를 client.get_messages(username, limit=N)으로 직접 읽음.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.types import Message

from backend.app.core.config import settings
from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    channel_id: int
    display_name: str
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)  # 저장된 raw_event ID 목록


class TelegramCollector:
    """Telethon MTProto 클라이언트를 통해 공개 채널 메시지 수집."""

    def __init__(self):
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        self.bot_token = settings.telegram_bot_token
        self._client: TelegramClient | None = None

    async def _get_client(self) -> TelegramClient:
        """StringSession + bot_token으로 Telethon 클라이언트 연결."""
        if self._client is not None and self._client.is_connected():
            return self._client

        self._client = TelegramClient(
            StringSession(""),
            self.api_id,
            self.api_hash,
            connection_retries=3,
            retry_delay=1,
        )
        await self._client.start(bot_token=self.bot_token)
        return self._client

    async def _disconnect(self):
        """클라이언트 연결 해제."""
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    def _parse_message(
        self,
        msg: Message,
        channel: SourceChannel,
    ) -> dict[str, Any] | None:
        """
        Telethon Message 객체 → raw_event 데이터 dict.
        미디어 전용 메시지 또는 빈 텍스트는 None 반환.
        """
        # 텍스트 추출 (text 우선, 없으면 caption)
        text = msg.text or ""
        if not text and hasattr(msg, "message"):
            text = msg.message or ""
        text = text.strip()

        if not text or len(text) < 10:
            return None

        # external_id: "-100{peer_id}_{message_id}" (기존 형식 호환)
        peer_id = msg.peer_id
        if hasattr(peer_id, "channel_id"):
            channel_id_num = peer_id.channel_id
        elif hasattr(peer_id, "chat_id"):
            channel_id_num = peer_id.chat_id
        else:
            channel_id_num = 0
        external_id = f"-100{channel_id_num}_{msg.id}"

        # 메타데이터 추출
        raw_metadata: dict[str, Any] = {
            "views": msg.views or 0,
            "forwards": msg.forwards or 0,
            "replies": msg.replies.replies if msg.replies else 0,
            "date": int(msg.date.timestamp()) if msg.date else None,
            "has_media": msg.media is not None,
        }

        return {
            "source_channel_id": channel.id,
            "source_type": "telegram",
            "external_id": external_id,
            "raw_text": text,
            "raw_metadata": raw_metadata,
            "lang": None,  # Normalizer에서 감지
            "collected_at": datetime.now(timezone.utc),
        }

    async def collect_channel(
        self,
        channel: SourceChannel,
        db: AsyncSession,
        client: TelegramClient,
        redis,
    ) -> CollectResult:
        """
        단일 채널의 최근 메시지를 수집.
        Redis에서 채널별 last_msg_id를 관리하여 중복 방지.
        """
        result = CollectResult(
            channel_id=channel.channel_id or 0,
            display_name=channel.display_name,
        )

        username = channel.username
        if not username:
            result.errors.append("username 미설정")
            return result

        # Redis에서 마지막 수집 메시지 ID 복원
        redis_key = f"telegram:last_msg_id:{username}"
        last_msg_id = 0
        if redis is not None:
            try:
                saved_id = await redis.get(redis_key)
                if saved_id:
                    last_msg_id = int(saved_id)
            except Exception as e:
                logger.warning("Redis last_msg_id 로드 실패 (%s): %s", username, e)

        # Telethon으로 메시지 조회
        try:
            messages = await asyncio.wait_for(
                client.get_messages(username, limit=50, min_id=last_msg_id),
                timeout=30,
            )
        except FloodWaitError as e:
            logger.warning("FloodWait %d초 - %s 건너뜀", e.seconds, username)
            result.errors.append(f"FloodWait {e.seconds}s")
            return result
        except asyncio.TimeoutError:
            logger.warning("Timeout - %s 메시지 조회 30초 초과", username)
            result.errors.append("Timeout 30s")
            return result
        except Exception as e:
            logger.error("채널 %s 메시지 조회 오류: %s", username, e)
            result.errors.append(str(e))
            return result

        if not messages:
            return result

        max_msg_id = last_msg_id

        for msg in messages:
            if not isinstance(msg, Message):
                continue

            parsed = self._parse_message(msg, channel)
            if parsed is None:
                result.skipped += 1
                continue

            # 중복 확인 (DB unique constraint)
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
            result.raw_event_ids.append(raw_event)
            result.collected += 1

            # 최대 메시지 ID 갱신
            if msg.id > max_msg_id:
                max_msg_id = msg.id

        # Redis에 최대 메시지 ID 저장 (7일 TTL)
        if max_msg_id > last_msg_id and redis is not None:
            try:
                await redis.set(redis_key, str(max_msg_id), ex=604800)
            except Exception as e:
                logger.warning("Redis last_msg_id 저장 실패 (%s): %s", username, e)

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[CollectResult]:
        """
        1. 설정 검증 (api_id, api_hash, bot_token)
        2. 활성 telegram 채널 조회
        3. Telethon 클라이언트 연결
        4. 채널별 순차 수집
        5. finally: disconnect
        """
        # 설정 검증
        if not self.api_id or not self.api_hash or not self.bot_token:
            logger.warning(
                "Telegram MTProto 설정 미완료 (api_id=%s, api_hash=%s, bot_token=%s) - 수집 건너뜀",
                bool(self.api_id),
                bool(self.api_hash),
                bool(self.bot_token),
            )
            return []

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

        # Telethon 클라이언트 연결
        try:
            client = await self._get_client()
        except Exception as e:
            logger.error("Telethon 클라이언트 연결 실패: %s", e)
            return []

        # 채널별 순차 수집
        results = []
        try:
            for channel in channels:
                try:
                    result = await self.collect_channel(channel, db, client, redis)
                    results.append(result)
                    logger.info(
                        "Telegram 수집 완료: %s (collected=%d, skipped=%d)",
                        channel.display_name,
                        result.collected,
                        result.skipped,
                    )
                    # Redis에 채널별 수집 상태 저장
                    await self._save_collect_status(
                        redis, channel.id, "ok", result.collected, result.skipped,
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
                    await self._save_collect_status(
                        redis, channel.id, "error", 0, 0, str(e),
                    )
        finally:
            await self._disconnect()

        return results

    @staticmethod
    async def _save_collect_status(
        redis, channel_id: int, status: str,
        collected: int, skipped: int, error: str = "",
    ):
        """Redis에 채널별 수집 상태 저장 (TTL 1시간)."""
        if redis is None:
            return
        try:
            key = f"collect:status:{channel_id}"
            value = json.dumps({
                "status": status,
                "collected": collected,
                "skipped": skipped,
                "error": error,
                "last_collected_at": datetime.now(timezone.utc).isoformat(),
            })
            await redis.set(key, value, ex=3600)
        except Exception as e:
            logger.warning("Redis 수집 상태 저장 실패 (channel=%s): %s", channel_id, e)
