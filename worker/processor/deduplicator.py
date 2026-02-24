"""
Deduplicator: dedup_key 기반 중복 탐지.

동일 dedup_key의 NormalizedEvent가 이미 존재하면 is_duplicate=True.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.normalized_event import NormalizedEvent

logger = logging.getLogger(__name__)


async def check_duplicate(dedup_key: str, db: AsyncSession) -> bool:
    """
    dedup_key로 중복 확인.
    비중복(is_duplicate=False)인 동일 dedup_key 레코드가 있으면 True.
    """
    result = await db.execute(
        select(NormalizedEvent).where(
            NormalizedEvent.dedup_key == dedup_key,
            NormalizedEvent.is_duplicate == False,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
