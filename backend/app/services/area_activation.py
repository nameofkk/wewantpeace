"""관심국가 활성/비활성 동기화 헬퍼."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import UserArea

logger = logging.getLogger(__name__)

PLAN_LIMITS: dict[str, int | None] = {
    "free": 2,
    "pro": 5,
    "pro_plus": None,
}


async def sync_area_activation(
    user_id: uuid.UUID,
    plan: str,
    db: AsyncSession,
) -> None:
    """플랜에 맞게 관심국가 is_active 플래그를 동기화.

    created_at 오름차순으로 정렬 후,
    플랜 한도 초과분을 is_active=False 처리.
    """
    result = await db.execute(
        select(UserArea)
        .where(UserArea.user_id == user_id)
        .order_by(UserArea.created_at.asc())
    )
    all_areas = result.scalars().all()
    limit = PLAN_LIMITS.get(plan.lower())

    changed = 0
    for i, area in enumerate(all_areas):
        should_be_active = limit is None or i < limit
        if area.is_active != should_be_active:
            area.is_active = should_be_active
            changed += 1

    if changed:
        logger.info(
            "sync_area_activation: user=%s plan=%s total=%d changed=%d",
            user_id, plan, len(all_areas), changed,
        )
    await db.flush()
