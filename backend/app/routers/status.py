"""
/status — 워커 헬스 스냅샷 읽기전용 노출 (관리자 전용).

worker/health/checker.py가 Redis에 쌓아둔 값만 읽어서 그대로 돌려준다.
이 엔드포인트는 절대 헬스체크를 새로 돌리지 않는다 (DB·외부 API 호출 없음, Redis read-only):
  - beat:heartbeat          → Beat 프로세스 심장박동 (TTL 10분)
  - celery:last_run:{task}  → 태스크별 마지막 실행 시각 (TTL 1시간)
  - health:last_results     → 19종 헬스체크 결과 스냅샷 (6시간마다 갱신)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response

from backend.app.core.auth import require_admin
from backend.app.core.limiter import limiter
from backend.app.core.redis import get_redis

router = APIRouter(prefix="/status", tags=["status"])

# checker.py와 동일한 키 (단일 출처). 값이 바뀌면 양쪽 다 맞춰야 함.
BEAT_HEARTBEAT_KEY = "beat:heartbeat"
LAST_RUN_PREFIX = "celery:last_run:"
HEALTH_SNAPSHOT_KEY = "health:last_results"

# beat heartbeat는 5분마다 갱신(TTL 10분). 이보다 오래되면 Beat 멈춤으로 본다.
_BEAT_STALE_SECONDS = 11 * 60
# 태스크 마지막 실행이 이보다 오래되면 "오래됨"으로 표시 (참고용, 태스크마다 주기 달라 일괄 기준).
_TASK_STALE_SECONDS = 6 * 60 * 60


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _age_seconds(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    return max(0, int((now - dt).total_seconds()))


@router.get("")
@limiter.limit("30/minute")
async def get_status(request: Request, response: Response, _admin=Depends(require_admin)):
    """워커 헬스 스냅샷 — Redis에 저장된 값만 읽어서 반환."""
    # 운영 모니터링용 — 캐시 금지 (항상 최신 스냅샷)
    response.headers["Cache-Control"] = "no-store"
    redis = get_redis()
    now = datetime.now(timezone.utc)

    # ── 1. Beat 심장박동 ──
    heartbeat_raw = await redis.get(BEAT_HEARTBEAT_KEY)
    heartbeat_dt = _parse_iso(heartbeat_raw)
    heartbeat_age = _age_seconds(heartbeat_dt, now)
    beat_ttl = await redis.ttl(BEAT_HEARTBEAT_KEY)
    beat_alive = heartbeat_dt is not None and heartbeat_age is not None and heartbeat_age <= _BEAT_STALE_SECONDS
    beat = {
        "alive": beat_alive,
        "last_heartbeat": heartbeat_dt.isoformat() if heartbeat_dt else None,
        "age_seconds": heartbeat_age,
        "ttl_seconds": beat_ttl if beat_ttl is not None and beat_ttl >= 0 else None,
    }

    # ── 2. 태스크별 마지막 실행 시각 ── (SCAN으로 키 전체 수집, KEYS 안 씀)
    tasks: dict[str, dict] = {}
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=f"{LAST_RUN_PREFIX}*", count=200)
        if keys:
            values = await redis.mget(keys)
            for key, raw in zip(keys, values):
                task_name = key[len(LAST_RUN_PREFIX):]
                dt = _parse_iso(raw)
                age = _age_seconds(dt, now)
                tasks[task_name] = {
                    "last_run": dt.isoformat() if dt else None,
                    "age_seconds": age,
                    "stale": age is None or age > _TASK_STALE_SECONDS,
                }
        if cursor == 0:
            break
    tasks = dict(sorted(tasks.items()))

    # ── 3. 19종 헬스체크 결과 스냅샷 ──
    snapshot_raw = await redis.get(HEALTH_SNAPSHOT_KEY)
    health: dict | None = None
    if snapshot_raw:
        try:
            health = json.loads(snapshot_raw)
            gen = _parse_iso(health.get("generated_at"))
            health["age_seconds"] = _age_seconds(gen, now)
        except (json.JSONDecodeError, AttributeError):
            health = None

    # ── 전체 상태 한 줄 요약 ──
    health_overall = health.get("overall") if health else None
    if not beat_alive or health_overall == "critical":
        overall = "down"
    elif health_overall == "warning" or health is None or any(t["stale"] for t in tasks.values()):
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "now": now.isoformat(),
        "overall": overall,
        "beat": beat,
        "tasks": tasks,
        "health": health,
    }
