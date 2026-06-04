"""
Deduplicator: dedup_key 기반 중복 탐지 (race-condition-safe).

동일 dedup_key의 NormalizedEvent가 이미 존재하면 is_duplicate=True.

TOCTTOU 방지:
  - SELECT ... FOR UPDATE로 동일 dedup_key 행을 잠금
  - 동시 INSERT 시 먼저 잠금을 획득한 트랜잭션만 비중복 판정
  - pg_advisory_xact_lock으로 아직 INSERT 안 된 경우도 직렬화
"""
import hashlib
import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.normalized_event import NormalizedEvent

logger = logging.getLogger(__name__)


def _dedup_lock_id(dedup_key: str) -> int:
    """dedup_key를 PostgreSQL advisory lock ID (bigint)로 변환."""
    # MD5 → 상위 8바이트 → signed int64
    h = hashlib.md5(dedup_key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=True)


async def check_duplicate(dedup_key: str, db: AsyncSession) -> bool:
    """
    dedup_key로 중복 확인 (race-condition-safe).

    1. pg_advisory_xact_lock으로 동일 dedup_key에 대한 동시 접근 직렬화
       (트랜잭션 종료 시 자동 해제)
    2. SELECT ... FOR UPDATE로 기존 비중복 레코드 잠금
    3. 기존 비중복 레코드가 있으면 True(중복), 없으면 False(신규)
    """
    lock_id = _dedup_lock_id(dedup_key)

    # 1. Advisory lock: 동일 dedup_key INSERT가 동시에 일어나도 직렬화
    await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

    # 2. 기존 비중복 레코드 확인 (FOR UPDATE로 잠금)
    result = await db.execute(
        select(NormalizedEvent).where(
            NormalizedEvent.dedup_key == dedup_key,
            NormalizedEvent.is_duplicate == False,
        ).limit(1).with_for_update()
    )
    return result.scalar_one_or_none() is not None
