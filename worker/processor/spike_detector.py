"""
SpikeDetector: Redis 카운터 기반 스파이크 감지.

알고리즘:
  c1  = 1분 이내 동일 cluster 이벤트 수  (Redis INCR, TTL 60s)
  c10 = 10분 이내 동일 cluster 이벤트 수 (Redis INCR, TTL 600s)
  b10 = 7일 시즌성 기준선 (없으면 EWMA 6h, alpha=0.3)

트리거: (c1 >= 4 OR c10 >= 12) AND ratio >= 4.0 AND severity >= 35
쿨다운: severity >= 90 → 30분, 그 외 → 1시간
"""
import logging
import math
import uuid as _uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────
C1_THRESHOLD = 4
C10_THRESHOLD = 12
RATIO_THRESHOLD = 4.0
SEVERITY_MIN = 35
COOLDOWN_SECONDS = 3600  # 1시간 (기본)
COOLDOWN_SECONDS_CRITICAL = 1800  # 30분 (severity >= 90)
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
        try:
            await redis.expire(k1, 60)
        except Exception as e:
            logger.error("Spike c1 expire 실패 (cluster=%s): %s", cluster_id, e)

    c10 = await redis.incr(k10)
    if c10 == 1:
        try:
            await redis.expire(k10, 600)
        except Exception as e:
            logger.error("Spike c10 expire 실패 (cluster=%s): %s", cluster_id, e)

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
    관측 횟수 기반 동적 alpha:
    - 관측 <5회: alpha=0.5 (빠른 적응)
    - 관측 ≥5회: alpha=0.3 (안정화)
    """
    old_b = await get_baseline(cluster_key, redis)

    # 관측 횟수 카운터
    obs_key = _key_obs_count(cluster_key)
    obs_count = await redis.incr(obs_key)
    if obs_count == 1:
        await redis.expire(obs_key, 24 * 3600)  # 24시간 TTL

    alpha = 0.5 if obs_count < 5 else EWMA_ALPHA
    new_b = alpha * c10 + (1 - alpha) * old_b
    new_b = round(new_b, 3)
    await redis.setex(_key_ewma(cluster_key), 6 * 3600, str(new_b))
    return new_b


async def is_in_cooldown(cluster_id: str, redis) -> bool:
    """쿨다운 중이면 True."""
    val = await redis.exists(_key_cooldown(cluster_id))
    return bool(val)


async def set_cooldown(cluster_id: str, redis, severity: int = 0):
    """쿨다운 설정. severity >= 90이면 30분, 그 외 1시간."""
    ttl = COOLDOWN_SECONDS_CRITICAL if severity >= 90 else COOLDOWN_SECONDS
    await redis.setex(_key_cooldown(cluster_id), ttl, "1")


def _key_sources(cluster_id: str) -> str:
    return f"spike:sources:{cluster_id}"


MIN_UNIQUE_SOURCES = 2


async def track_source(cluster_id: str, source_id: str, redis):
    """10분 윈도우 내 소스 ID 추적."""
    key = _key_sources(cluster_id)
    await redis.sadd(key, source_id)
    await redis.expire(key, 600)  # 10분 TTL


async def get_unique_source_count(cluster_id: str, redis) -> int:
    """10분 윈도우 내 고유 소스 수."""
    return await redis.scard(_key_sources(cluster_id))


def _key_obs_count(cluster_key: str) -> str:
    return f"spike:obs_count:{cluster_key}"


async def _save_spike_event(
    cluster_id: str,
    severity: int,
    kscore: float,
    c1: int,
    c10: int,
    baseline: float,
    ratio: float,
    unique_sources: int,
) -> str:
    """Save spike event to DB and return its ID as string."""
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.spike_event import SpikeEvent

    async with AsyncSessionLocal() as db:
        async with db.begin():
            event = SpikeEvent(
                cluster_id=_uuid.UUID(cluster_id),
                severity=severity,
                kscore=kscore,
                c1=c1,
                c10=c10,
                baseline=baseline,
                ratio=ratio,
                unique_sources=unique_sources,
            )
            db.add(event)
            await db.flush()
            return str(event.id)


async def evaluate_spike(
    cluster_id: str,
    cluster_key: str,
    severity: int,
    redis,
    source_id: str = "",
    kscore: float = 0.0,
) -> tuple[bool, str | None]:
    """
    스파이크 조건 평가.
    Returns (triggered, spike_event_id).
    triggered=True 시 cluster.is_spike = True 로 업데이트해야 함.
    """
    # 쿨다운 확인
    if await is_in_cooldown(cluster_id, redis):
        return False, None

    # 소스 추적
    if source_id:
        await track_source(cluster_id, source_id, redis)

    # 카운터 증가
    c1, c10 = await increment_event_counters(cluster_id, redis)

    # 기준선
    b10 = await get_baseline(cluster_key, redis)
    await update_baseline(cluster_key, c10, redis)

    ratio = c10 / (b10 + 1)

    # 소스 다양성 체크: 최소 2개 독립 소스 필요 (가짜 스파이크 방지)
    unique_sources = await get_unique_source_count(cluster_id, redis)

    triggered = (
        (c1 >= C1_THRESHOLD or c10 >= C10_THRESHOLD)
        and ratio >= RATIO_THRESHOLD
        and severity >= SEVERITY_MIN
        and unique_sources >= MIN_UNIQUE_SOURCES
    )

    logger.debug(
        "spike_eval cluster=%s c1=%d c10=%d b10=%.2f ratio=%.2f sev=%d sources=%d -> %s",
        cluster_id, c1, c10, b10, ratio, severity, unique_sources, triggered,
    )

    spike_event_id: str | None = None
    if triggered:
        await set_cooldown(cluster_id, redis, severity=severity)
        try:
            spike_event_id = await _save_spike_event(
                cluster_id=cluster_id,
                severity=severity,
                kscore=kscore,
                c1=c1,
                c10=c10,
                baseline=b10,
                ratio=ratio,
                unique_sources=unique_sources,
            )
            logger.info(
                "SpikeEvent 저장: id=%s cluster=%s sev=%d",
                spike_event_id, cluster_id, severity,
            )
        except Exception as e:
            logger.error("SpikeEvent 저장 실패 (무시): %s", e)

    return triggered, spike_event_id
