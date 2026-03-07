"""
SpikeDetector: 누적 기반 스파이크 감지.

알고리즘 (v2 — RSS 배치 수집 환경에 맞게 재설계):
  기존: Redis c1/c10 실시간 카운터 → RSS 5분 배치에서 절대 발동 불가
  변경: 클러스터 누적 상태(event_count, severity, independent_sources)로 판단

트리거 조건 (모두 충족):
  event_count >= 8          — 보도 건수 충분 (v5: 5→8)
  severity >= 40            — 최소 위험도
  independent_sources >= 3  — 복수 독립 출처 (v5: 2→3)
  cluster age <= 48h        — 최근 클러스터만 (오래된 건 제외)

쿨다운: severity >= 90 → 30분, 그 외 → 1시간 (Redis 유지)
"""
import logging
import uuid as _uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────
# v5 (소스 확장): 5→8, 2→3 (58개 소스에서 스파이크 남발 방지)
EVENT_COUNT_MIN = 8
SEVERITY_MIN = 40
SOURCES_MIN = 3
MAX_AGE_HOURS = 48

COOLDOWN_SECONDS = 21600  # 6시간 (기본) — 같은 이슈 반복 방지
COOLDOWN_SECONDS_CRITICAL = 10800  # 3시간 (severity >= 90)


def _key_cooldown(cluster_id: str) -> str:
    return f"spike:cooldown:{cluster_id}"


async def is_in_cooldown(cluster_id: str, redis) -> bool:
    """쿨다운 중이면 True."""
    val = await redis.exists(_key_cooldown(cluster_id))
    return bool(val)


async def set_cooldown(cluster_id: str, redis, severity: int = 0):
    """쿨다운 설정. severity >= 90이면 30분, 그 외 1시간."""
    ttl = COOLDOWN_SECONDS_CRITICAL if severity >= 90 else COOLDOWN_SECONDS
    await redis.setex(_key_cooldown(cluster_id), ttl, "1")


async def _save_spike_event(
    cluster_id: str,
    severity: int,
    kscore: float,
    event_count: int,
    independent_sources: int,
    age_hours: float,
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
                c1=event_count,           # 재활용: event_count
                c10=independent_sources,  # 재활용: independent_sources
                baseline=age_hours,       # 재활용: cluster age (hours)
                ratio=0.0,
                unique_sources=independent_sources,
            )
            db.add(event)
            await db.flush()
            return str(event.id)


async def evaluate_spike(
    cluster_id: str,
    severity: int,
    event_count: int,
    independent_sources: int,
    first_event_at: datetime | None,
    kscore: float = 0.0,
    redis=None,
    # legacy params (무시, 호환성용)
    cluster_key: str = "",
    source_id: str = "",
) -> tuple[bool, str | None]:
    """
    누적 기반 스파이크 조건 평가.
    Returns (triggered, spike_event_id).
    triggered=True 시 cluster.is_spike = True 로 업데이트해야 함.
    """
    # 이미 스파이크면 다시 평가 불필요 (쿨다운으로 처리)
    if redis and await is_in_cooldown(cluster_id, redis):
        return False, None

    # 클러스터 나이 계산
    now = datetime.now(timezone.utc)
    if first_event_at:
        age_hours = (now - first_event_at).total_seconds() / 3600
    else:
        age_hours = 0.0

    triggered = (
        event_count >= EVENT_COUNT_MIN
        and severity >= SEVERITY_MIN
        and independent_sources >= SOURCES_MIN
        and age_hours <= MAX_AGE_HOURS
    )

    logger.debug(
        "spike_eval cluster=%s ev=%d sev=%d sources=%d age=%.1fh ks=%.1f -> %s",
        cluster_id, event_count, severity, independent_sources, age_hours, kscore, triggered,
    )

    spike_event_id: str | None = None
    if triggered:
        if redis:
            await set_cooldown(cluster_id, redis, severity=severity)
        try:
            spike_event_id = await _save_spike_event(
                cluster_id=cluster_id,
                severity=severity,
                kscore=kscore,
                event_count=event_count,
                independent_sources=independent_sources,
                age_hours=age_hours,
            )
            logger.info(
                "SpikeEvent 저장: id=%s cluster=%s sev=%d ev=%d sources=%d",
                spike_event_id, cluster_id, severity, event_count, independent_sources,
            )
        except Exception as e:
            logger.error("SpikeEvent 저장 실패 (무시): %s", e)

    return triggered, spike_event_id
