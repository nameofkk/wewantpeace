"""
/status — 워커 헬스 스냅샷 읽기전용 노출 (관리자 전용).

worker/health/checker.py가 Redis에 쌓아둔 값만 읽어서 그대로 돌려준다.
이 엔드포인트는 절대 헬스체크를 새로 돌리지 않는다 (DB·외부 API 호출 없음, Redis read-only):
  - beat:heartbeat          → Beat 프로세스 심장박동 (TTL 10분)
  - celery:last_run:{task}  → 태스크별 마지막 실행 시각 (TTL 1시간)
  - health:last_results     → 19종 헬스체크 결과 스냅샷 (6시간마다 갱신)

가용성(available)은 "엔드포인트가 응답하냐"가 아니라 "마지막 수집이 N분 이내냐"로 판정한다.
응답에는 지금 떠 있는 배포 커밋 SHA(version)도 같이 박아서, 어떤 코드가 도는지 바로 보이게 한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response

from backend.app.core.auth import require_admin
from backend.app.core.config import settings
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

# 수집 태스크 이름은 worker/tasks.py에서 "collect_" 접두사로 heartbeat를 찍는다.
# (collect_rss / collect_telegram_channels / collect_gdelt / collect_usgs / ...)
_COLLECTION_TASK_PREFIX = "collect_"
# 가용성 기준: 마지막 수집이 이 시간 안에 일어났는지로 판정한다.
# collect_rss·collect_telegram이 5분 주기라, 3주기(15분) 동안 한 번도 못 들어오면 "수집 끊김"으로 본다.
_COLLECTION_STALE_SECONDS = 15 * 60


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

    # ── 2-1. 가용성 = "마지막 수집이 N분 이내인가" ──
    # 엔드포인트가 200을 주는지(=응답 여부)로 살았다/죽었다를 판단하지 않는다.
    # 진짜 기준은 데이터가 실제로 들어오고 있냐다. collect_* 태스크 중 제일 최근에 돈 걸 잡아서,
    # 그게 _COLLECTION_STALE_SECONDS 안이면 "수집 살아있음(available)"으로 본다.
    last_collection_task: str | None = None
    last_collection_age: int | None = None
    last_collection_iso: str | None = None
    for name, info in tasks.items():
        if not name.startswith(_COLLECTION_TASK_PREFIX):
            continue
        age = info["age_seconds"]
        if age is None:
            continue
        if last_collection_age is None or age < last_collection_age:
            last_collection_age = age
            last_collection_task = name
            last_collection_iso = info["last_run"]
    available = last_collection_age is not None and last_collection_age <= _COLLECTION_STALE_SECONDS
    collection = {
        "available": available,
        "last_collection": last_collection_iso,
        "age_seconds": last_collection_age,
        "source_task": last_collection_task,
        "threshold_seconds": _COLLECTION_STALE_SECONDS,
    }

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
    # 가용성(수집이 N분 이내인가)을 1순위 기준으로 둔다. 수집이 끊겼으면 beat가 뛰든 엔드포인트가
    # 200을 주든 상관없이 "down" — 신선한 데이터를 못 내보내는 상태라서.
    health_overall = health.get("overall") if health else None
    if not available or not beat_alive or health_overall == "critical":
        overall = "down"
    elif health_overall == "warning" or health is None or any(t["stale"] for t in tasks.values()):
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "now": now.isoformat(),
        "overall": overall,
        # 배포된 커밋 식별자 — 지금 어떤 코드가 떠 있는지 응답만 보고 바로 알 수 있게 박는다.
        "version": {
            "commit": settings.commit_sha or None,
            "commit_short": settings.commit_short or None,
        },
        "available": available,
        "collection": collection,
        "beat": beat,
        "tasks": tasks,
        "health": health,
    }
