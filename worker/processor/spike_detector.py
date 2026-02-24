"""
SpikeDetector: Redis 카운터 기반 스파이크 감지.

알고리즘:
  c1  = 1분 이내 동일 cluster 이벤트 수  (Redis INCR, TTL 60s)
  c10 = 10분 이내 동일 cluster 이벤트 수 (Redis INCR, TTL 600s)
  b10 = 7일 시즌성 기준선 (없으면 EWMA 6h, alpha=0.3)

트리거: (c1 >= 4 OR c10 >= 12) AND ratio >= 4.0 AND severity >= 35
쿨다운: 동일 cluster 15분 (Redis key로 관리)
"""
import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────
C1_THRESHOLD = 4
C10_THRESHOLD = 12
RATIO_THRESHOLD = 4.0
SEVERITY_MIN = 35
COOLDOWN_SECONDS = 3600  # 1시간
EWMA_ALPHA = 0.3

# Redis 키 패턴
def _key_c1(cluster_id: str) -> str:
    return f"spike:c1:{cluster_id}"

def _key_c10(cluster_id: str) -> str:
    return f"spike:c10:{cluster_id}"

def _key_ewma(cluster_key: str) -> str:
    return f"spike:ewma:{cluster_key}"

def _key_cooldown(cluster_id: str) -> str:
    return f"spike:cooldown:{cluster_id}"


async def increment_event_counters(cluster_id: str, redis) -> tuple[int, int]:
    """
    c1(1분), c10(10분) 카운터 증가.
    INCR 후 카운터가 1(신규)이면 EXPIRE 설정 — 원자성 보장.
    Returns (c1, c10).
    """
    k1 = _key_c1(cluster_id)
    k10 = _key_c10(cluster_id)

    c1 = await redis.incr(k1)
    if c1 == 1:
        await redis.expire(k1, 60)

    c10 = await redis.incr(k10)
    if c10 == 1:
        await redis.expire(k10, 600)

    return int(c1), int(c10)


async def get_baseline(cluster_key: str, redis) -> float:
    """
    EWMA 6h 기준선 조회. 없으면 0 반환.
    """
    val = await redis.get(_key_ewma(cluster_key))
    return float(val) if val else 0.0


async def update_baseline(cluster_key: str, c10: int, redis) -> float:
    """
    EWMA 기준선 업데이트: new_b = alpha * c10 + (1 - alpha) * old_b
    """
    old_b = await get_baseline(cluster_key, redis)
    new_b = EWMA_ALPHA * c10 + (1 - EWMA_ALPHA) * old_b
    new_b = round(new_b, 3)
    await redis.setex(_key_ewma(cluster_key), 6 * 3600, str(new_b))
    return new_b


async def is_in_cooldown(cluster_id: str, redis) -> bool:
    """15분 쿨다운 중이면 True."""
    val = await redis.exists(_key_cooldown(cluster_id))
    return bool(val)


async def set_cooldown(cluster_id: str, redis):
    """쿨다운 설정 (15분)."""
    await redis.setex(_key_cooldown(cluster_id), COOLDOWN_SECONDS, "1")


async def evaluate_spike(
    cluster_id: str,
    cluster_key: str,
    severity: int,
    redis,
) -> bool:
    """
    스파이크 조건 평가.
    True 반환 시 cluster.is_spike = True 로 업데이트해야 함.
    """
    # 쿨다운 확인
    if await is_in_cooldown(cluster_id, redis):
        return False

    # 카운터 증가
    c1, c10 = await increment_event_counters(cluster_id, redis)

    # 기준선
    b10 = await get_baseline(cluster_key, redis)
    await update_baseline(cluster_key, c10, redis)

    ratio = c10 / (b10 + 1)

    triggered = (
        (c1 >= C1_THRESHOLD or c10 >= C10_THRESHOLD)
        and ratio >= RATIO_THRESHOLD
        and severity >= SEVERITY_MIN
    )

    logger.debug(
        "spike_eval cluster=%s c1=%d c10=%d b10=%.2f ratio=%.2f sev=%d -> %s",
        cluster_id, c1, c10, b10, ratio, severity, triggered,
    )

    if triggered:
        await set_cooldown(cluster_id, redis)

    return triggered
