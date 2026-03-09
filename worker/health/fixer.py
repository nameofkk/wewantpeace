"""자동 수정 실행기 — 승인된 action을 실행.

Telegram 승인을 받은 후 notifier.py에서 호출됩니다.
각 action은 독립적이며, 실패 시에도 다른 action에 영향을 주지 않습니다.
"""
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.redis import get_redis

logger = logging.getLogger(__name__)


async def execute_fix(action: str, params: dict) -> str:
    """승인된 수정 action 실행. 결과 메시지를 반환."""
    handlers = {
        "reactivate_channels": _fix_reactivate_channels,
        "reprocess_topics": _fix_reprocess_topics,
        "split_mega_cluster": _fix_split_mega_cluster,
        "reset_openai_rate_limit": _fix_reset_openai_rate_limit,
    }

    handler = handlers.get(action)
    if not handler:
        return f"알 수 없는 action: {action}"

    try:
        result = await handler(params)
        logger.info("자동 수정 완료: action=%s, result=%s", action, result)
        return result
    except Exception as e:
        logger.exception("자동 수정 실패: action=%s", action)
        return f"수정 실패: {type(e).__name__}: {e}"


# ── Action: reactivate_channels ─────────────────────────────────────────────


async def _fix_reactivate_channels(params: dict) -> str:
    """지정된 channel_ids를 is_active=true로 변경 + Redis 에러 카운트 리셋."""
    channel_ids = params.get("channel_ids", [])
    if not channel_ids:
        return "재활성화할 채널 없음"

    redis = get_redis()
    recovered = []

    async with AsyncSessionLocal() as db:
        for cid in channel_ids:
            try:
                await db.execute(
                    text(
                        "UPDATE source_channels"
                        " SET is_active = true, updated_at = :now"
                        " WHERE id = :cid AND is_active = false"
                    ),
                    {"cid": cid, "now": datetime.now(timezone.utc)},
                )
                # Redis 에러 카운트 리셋
                try:
                    await redis.delete(f"rss:consecutive_errors:{cid}")
                except Exception:
                    pass
                recovered.append(cid)
            except Exception as e:
                logger.warning("채널 %s 재활성화 실패: %s", cid, e)

        if recovered:
            await db.commit()

    return f"채널 {len(recovered)}개 재활성화 완료: {recovered}"


# ── Action: reprocess_topics ────────────────────────────────────────────────


async def _fix_reprocess_topics(params: dict) -> str:
    """reprocess_topics.py를 subprocess로 실행."""
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "scripts",
        "reprocess_topics.py",
    )

    if not os.path.exists(script_path):
        return f"스크립트 미발견: {script_path}"

    # DATABASE_URL 환경변수 설정
    env = os.environ.copy()
    db_url = env.get("DATABASE_URL", "")
    if not db_url:
        # config에서 가져오기 시도
        try:
            from backend.app.core.config import settings
            # asyncpg -> psycopg2 변환 (subprocess는 sync)
            db_url = settings.database_url
        except Exception:
            pass

    if db_url:
        env["DATABASE_URL"] = db_url

    try:
        # subprocess로 실행 (타임아웃 5분)
        result = subprocess.run(
            [sys.executable, script_path, "--all"],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        if result.returncode == 0:
            # 마지막 몇 줄만 반환
            output_lines = result.stdout.strip().split("\n")
            summary = "\n".join(output_lines[-5:]) if len(output_lines) > 5 else result.stdout.strip()
            return f"reprocess 완료:\n{summary}"
        else:
            stderr = result.stderr.strip()[-300:] if result.stderr else "no stderr"
            return f"reprocess 실패 (exit={result.returncode}):\n{stderr}"

    except subprocess.TimeoutExpired:
        return "reprocess 타임아웃 (5분 초과)"
    except Exception as e:
        return f"reprocess 실행 오류: {type(e).__name__}: {e}"


# ── Action: split_mega_cluster ──────────────────────────────────────────────


async def _fix_split_mega_cluster(params: dict) -> str:
    """event_count > 50인 클러스터의 가장 오래된 이벤트들을 분리 (비활성화)."""
    cluster_ids = params.get("cluster_ids", [])
    if not cluster_ids:
        return "분할할 클러스터 없음"

    trimmed = 0
    async with AsyncSessionLocal() as db:
        for cid in cluster_ids:
            try:
                # 클러스터의 이벤트 중 가장 오래된 것들 (50개 초과분)을 cluster_events에서 제거
                # 먼저 현재 이벤트 수 확인
                count_q = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM cluster_events WHERE cluster_id = :cid"
                    ),
                    {"cid": cid},
                )
                event_count = count_q.scalar() or 0

                if event_count <= 50:
                    continue

                excess = event_count - 50

                # 가장 오래된 이벤트들의 ID 조회
                old_events_q = await db.execute(
                    text("""
                        SELECT ce.event_id FROM cluster_events ce
                        JOIN normalized_events ne ON ce.event_id = ne.id
                        WHERE ce.cluster_id = :cid
                        ORDER BY ne.event_time ASC
                        LIMIT :excess
                    """),
                    {"cid": cid, "excess": excess},
                )
                old_event_ids = [row.event_id for row in old_events_q.fetchall()]

                if old_event_ids:
                    # cluster_events에서 제거
                    await db.execute(
                        text(
                            "DELETE FROM cluster_events"
                            " WHERE cluster_id = :cid"
                            " AND event_id = ANY(:eids)"
                        ),
                        {"cid": cid, "eids": old_event_ids},
                    )

                    # 클러스터 event_count 업데이트
                    await db.execute(
                        text(
                            "UPDATE issue_clusters SET event_count = 50,"
                            " updated_at = :now"
                            " WHERE id = :cid"
                        ),
                        {"cid": cid, "now": datetime.now(timezone.utc)},
                    )
                    trimmed += len(old_event_ids)

            except Exception as e:
                logger.warning("클러스터 %s 분할 실패: %s", cid, e)
                try:
                    await db.rollback()
                except Exception:
                    pass

        if trimmed:
            await db.commit()

    return f"메가 클러스터 {len(cluster_ids)}개에서 {trimmed}개 이벤트 분리 완료"


# ── Action: reset_openai_rate_limit ─────────────────────────────────────────


async def _fix_reset_openai_rate_limit(params: dict) -> str:
    """OpenAI API 에러 카운트 리셋 + 상태 확인."""
    redis = get_redis()
    reset_keys = []

    try:
        # OpenAI 관련 Redis 카운터 리셋
        for pattern in ["openai:*error*", "openai:*fail*", "openai:*rate*"]:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    for key in keys:
                        await redis.delete(key)
                        reset_keys.append(key)
                    if cursor == 0:
                        break
            except Exception:
                pass

        # 성공/실패 카운터 리셋
        for key in ["openai:classify:success_1h", "openai:classify:failure_1h"]:
            try:
                await redis.delete(key)
                reset_keys.append(key)
            except Exception:
                pass

    except Exception as e:
        return f"Redis 리셋 오류: {e}"

    return f"OpenAI 에러 카운터 {len(reset_keys)}개 리셋 완료"
