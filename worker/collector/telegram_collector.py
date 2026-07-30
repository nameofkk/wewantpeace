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

# 연속 resolve 실패 N회 초과 시 자동 비활성화 (15분 주기 × 20 = 5시간)
_MAX_RESOLVE_FAILURES = 20


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
        self.session_str = settings.telegram_session
        self._client: TelegramClient | None = None

    async def _get_client(self) -> TelegramClient:
        """StringSession(유저 계정)으로 Telethon 클라이언트 연결."""
        if self._client is not None and self._client.is_connected():
            return self._client

        self._client = TelegramClient(
            StringSession(self.session_str),
            self.api_id,
            self.api_hash,
            connection_retries=3,
            retry_delay=1,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError("Telegram 세션이 유효하지 않습니다. TELEGRAM_SESSION을 재생성하세요.")
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

    async def _get_fail_count(self, redis, channel_id: int) -> int:
        """Redis에서 연속 resolve 실패 횟수 조회."""
        if redis is None:
            return 0
        try:
            val = await redis.get(f"telegram:resolve_fails:{channel_id}")
            return int(val) if val else 0
        except Exception:
            return 0

    async def _increment_fail_count(self, redis, channel_id: int) -> int:
        """연속 실패 횟수 증가. 반환값: 증가 후 횟수."""
        if redis is None:
            return 0
        try:
            key = f"telegram:resolve_fails:{channel_id}"
            count = await redis.incr(key)
            await redis.expire(key, 86400)  # 24시간 TTL
            return count
        except Exception:
            return 0

    async def _reset_fail_count(self, redis, channel_id: int):
        """resolve 성공 시 실패 횟수 리셋."""
        if redis is None:
            return
        try:
            await redis.delete(f"telegram:resolve_fails:{channel_id}")
        except Exception:
            pass

    async def _resolve_entity(
        self,
        channel: SourceChannel,
        client: TelegramClient,
        db: AsyncSession,
        redis=None,
    ):
        """
        채널 엔티티 해석 + channel_id/username 자동 동기화.

        우선순위: channel_id(영구) > username(가변)
        성공 시 DB에 channel_id와 최신 username을 자동 저장.
        연속 실패 시 자동 비활성화.
        """
        entity = None

        # 1) channel_id가 있으면 우선 사용 (영구 불변)
        #    Telethon resolve_id()는 양수를 PeerUser로 해석하므로
        #    채널 ID는 Bot API 마킹 형식(-100 prefix)으로 변환 필요
        if channel.channel_id:
            try:
                marked_id = -1_000_000_000_000 - channel.channel_id
                entity = await client.get_entity(marked_id)
            except Exception as e:
                logger.warning(
                    "channel_id %s로 엔티티 해석 실패 (%s), username fallback",
                    channel.channel_id, e,
                )

        # 2) channel_id 실패 또는 없으면 username으로 시도
        if entity is None and channel.username:
            try:
                entity = await client.get_entity(channel.username)
            except Exception as e:
                logger.error(
                    "채널 %s (username=%s) 엔티티 해석 실패: %s",
                    channel.display_name, channel.username, e,
                )

        # 3) 둘 다 실패 → 연속 실패 카운트 증가, 임계치 초과 시 자동 비활성화
        if entity is None:
            fail_count = await self._increment_fail_count(redis, channel.id)
            if fail_count >= _MAX_RESOLVE_FAILURES:
                logger.warning(
                    "채널 %s resolve 연속 %d회 실패 → 자동 비활성화 (channel_id=%s, username=%s)",
                    channel.display_name, fail_count, channel.channel_id, channel.username,
                )
                channel.is_active = False
                db.add(channel)
                await db.flush()
            else:
                logger.warning(
                    "채널 %s resolve 실패 (%d/%d) — channel_id=%s, username=%s",
                    channel.display_name, fail_count, _MAX_RESOLVE_FAILURES,
                    channel.channel_id, channel.username,
                )
            return None

        # resolve 성공 → 실패 카운트 리셋
        await self._reset_fail_count(redis, channel.id)

        # 4) DB에 channel_id / username 자동 동기화
        resolved_id = getattr(entity, "id", None)
        resolved_username = getattr(entity, "username", None)
        updated = False

        if resolved_id and channel.channel_id != resolved_id:
            logger.info(
                "채널 %s channel_id 자동 저장: %s",
                channel.display_name, resolved_id,
            )
            channel.channel_id = resolved_id
            updated = True

        # username 변경 감지 (삭제된 경우도 포함)
        if resolved_username != channel.username:
            if resolved_username:
                logger.info(
                    "채널 %s username 자동 갱신: %s → %s",
                    channel.display_name, channel.username, resolved_username,
                )
            else:
                logger.warning(
                    "채널 %s username 삭제 감지 (기존: %s) — channel_id=%s로 수집 지속",
                    channel.display_name, channel.username, channel.channel_id,
                )
            channel.username = resolved_username
            updated = True

        if updated:
            db.add(channel)
            await db.flush()

        return entity

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

        if not channel.username and not channel.channel_id:
            result.errors.append("username/channel_id 미설정")
            return result

        # 채널 엔티티 해석 (channel_id 우선, username fallback, 자동 동기화)
        entity = await self._resolve_entity(channel, client, db, redis)
        if entity is None:
            result.errors.append("채널 엔티티 해석 실패")
            return result

        # Redis 키는 channel_id 기반 (영구 불변)으로 사용
        stable_key = str(channel.channel_id) if channel.channel_id else channel.username
        redis_key = f"telegram:last_msg_id:{stable_key}"
        last_msg_id = 0
        if redis is not None:
            try:
                saved_id = await redis.get(redis_key)
                if saved_id:
                    last_msg_id = int(saved_id)
                # username 기반 이전 키에서 마이그레이션
                if not saved_id and channel.channel_id and channel.username:
                    old_key = f"telegram:last_msg_id:{channel.username}"
                    old_val = await redis.get(old_key)
                    if old_val:
                        last_msg_id = int(old_val)
                        await redis.set(redis_key, old_val, ex=604800)
                        await redis.delete(old_key)
                        logger.info("Redis 키 마이그레이션: %s → %s", old_key, redis_key)
            except Exception as e:
                logger.warning("Redis last_msg_id 로드 실패 (%s): %s", stable_key, e)

        # Telethon으로 메시지 조회 (entity 직접 사용)
        try:
            messages = await asyncio.wait_for(
                client.get_messages(entity, limit=50, min_id=last_msg_id),
                timeout=30,
            )
        except FloodWaitError as e:
            # 지수 백오프 재시도 (최대 2회)
            for attempt in range(1, 3):
                wait = min(e.seconds * attempt, 90)
                logger.warning("FloodWait %d초 (대기 %d초, attempt %d/2) - %s", e.seconds, wait, attempt, channel.display_name)
                await asyncio.sleep(wait)
                try:
                    messages = await asyncio.wait_for(
                        client.get_messages(entity, limit=50, min_id=last_msg_id),
                        timeout=30,
                    )
                    break  # 성공
                except FloodWaitError as e2:
                    e = e2  # 다음 루프에서 사용
                    continue
                except Exception:
                    result.errors.append(f"FloodWait {e.seconds}s (retry {attempt} failed)")
                    return result
            else:
                result.errors.append(f"FloodWait {e.seconds}s (all retries failed)")
                return result
        except asyncio.TimeoutError:
            logger.warning("Timeout - %s 메시지 조회 30초 초과", channel.display_name)
            result.errors.append("Timeout 30s")
            return result
        except Exception as e:
            logger.error("채널 %s 메시지 조회 오류: %s", channel.display_name, e)
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
                logger.warning("Redis last_msg_id 저장 실패 (%s): %s", stable_key, e)

        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[CollectResult]:
        """
        1. 설정 검증 (api_id, api_hash, session)
        2. 활성 telegram 채널 조회
        3. Telethon 클라이언트 연결
        4. 채널별 순차 수집
        5. finally: disconnect
        """
        # 설정 검증
        if not self.api_id or not self.api_hash or not self.session_str:
            logger.warning(
                "Telegram MTProto 설정 미완료 (api_id=%s, api_hash=%s, session=%s) - 수집 건너뜀",
                bool(self.api_id),
                bool(self.api_hash),
                bool(self.session_str),
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
                    # 채널 하나가 끝날 때마다 트랜잭션을 닫는다.
                    # 예전에는 18개 채널 전체(네트워크 대기 포함)가 한 트랜잭션으로 묶여
                    # 그동안 Supavisor 커넥션을 계속 붙잡고 있었다.
                    # RSS 수집이 이미 피드별 커밋으로 도는 것과 같은 방식.
                    # expire_on_commit=False라 raw_event_ids의 .id는 커밋 후에도 그대로 읽힌다.
                    await db.commit()
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
