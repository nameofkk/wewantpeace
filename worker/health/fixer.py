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
        "cleanup_stale_fcm_tokens": _fix_cleanup_stale_fcm_tokens,
        "expire_stale_subscriptions": _fix_expire_stale_subscriptions,
        "recalculate_tension": _fix_recalculate_tension,
        "cleanup_redis_keys": _fix_cleanup_redis_keys,
        "reprocess_orphans": _fix_reprocess_orphans,
        "retry_sns_publish": _fix_retry_sns_publish,
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


# ── Action: cleanup_stale_fcm_tokens ──────────────────────────────────────


async def _fix_cleanup_stale_fcm_tokens(params: dict) -> str:
    """alert_delivery_log에서 만료/미등록 토큰 감지 → user_push_tokens에서 삭제."""
    try:
        async with AsyncSessionLocal() as db:
            # failure_reason에 'token_expired' 또는 'NotRegistered' 포함하는 유저 추출
            stale_q = await db.execute(
                text("""
                    SELECT DISTINCT adl.user_id
                    FROM alert_delivery_log adl
                    WHERE adl.failure_reason IS NOT NULL
                      AND (
                          adl.failure_reason ILIKE '%token_expired%'
                          OR adl.failure_reason ILIKE '%NotRegistered%'
                      )
                """)
            )
            user_ids = [row.user_id for row in stale_q.fetchall()]

            if not user_ids:
                return "만료된 FCM 토큰 없음"

            # user_push_tokens에서 해당 유저의 토큰 삭제
            result = await db.execute(
                text(
                    "DELETE FROM user_push_tokens"
                    " WHERE user_id = ANY(:uids)"
                    " AND status != 'active'"
                ),
                {"uids": user_ids},
            )
            deleted_inactive = result.rowcount or 0

            # 실패 기록이 있는 유저의 오래된 토큰도 정리 (30일 이상 미사용)
            result2 = await db.execute(
                text(
                    "DELETE FROM user_push_tokens"
                    " WHERE user_id = ANY(:uids)"
                    " AND last_used < NOW() - INTERVAL '30 days'"
                ),
                {"uids": user_ids},
            )
            deleted_old = result2.rowcount or 0

            await db.commit()

        total = deleted_inactive + deleted_old
        return f"FCM 토큰 정리 완료: 유저 {len(user_ids)}명, 삭제 {total}개 (비활성 {deleted_inactive} + 미사용 {deleted_old})"

    except Exception as e:
        if "does not exist" in str(e) or "relation" in str(e).lower():
            return "토큰 관리 모델 미발견 (user_push_tokens 테이블 없음)"
        raise


# ── Action: expire_stale_subscriptions ────────────────────────────────────


async def _fix_expire_stale_subscriptions(params: dict) -> str:
    """만료일 지난 active 구독을 expired로 변경 + 유저 plan을 free로 다운그레이드."""
    async with AsyncSessionLocal() as db:
        try:
            # 1) 만료된 구독 찾기
            expired_q = await db.execute(
                text("""
                    SELECT id, user_id, plan
                    FROM subscriptions
                    WHERE status = 'active'
                      AND expires_at IS NOT NULL
                      AND expires_at < NOW()
                """)
            )
            expired_rows = expired_q.fetchall()

            if not expired_rows:
                return "만료 처리할 구독 없음"

            sub_ids = [row.id for row in expired_rows]
            user_ids = list({row.user_id for row in expired_rows})

            # 2) 구독 상태 → expired
            await db.execute(
                text(
                    "UPDATE subscriptions"
                    " SET status = 'expired', updated_at = :now"
                    " WHERE id = ANY(:sids)"
                ),
                {"sids": sub_ids, "now": datetime.now(timezone.utc)},
            )

            # 3) 해당 유저의 plan → free (다른 active 구독이 없는 경우만)
            downgraded = 0
            for uid in user_ids:
                active_check = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM subscriptions"
                        " WHERE user_id = :uid AND status = 'active'"
                    ),
                    {"uid": uid},
                )
                if (active_check.scalar() or 0) == 0:
                    await db.execute(
                        text(
                            "UPDATE users SET plan = 'free'"
                            " WHERE id = :uid AND plan != 'free'"
                        ),
                        {"uid": uid},
                    )
                    downgraded += 1

            await db.commit()

            return (
                f"구독 만료 처리 완료: {len(sub_ids)}건 expired, "
                f"{downgraded}명 free 다운그레이드"
            )

        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            if "does not exist" in str(e):
                return "subscriptions 테이블 미발견"
            raise


# ── Action: recalculate_tension ───────────────────────────────────────────


async def _fix_recalculate_tension(params: dict) -> str:
    """긴장도 지수 재계산을 Celery 태스크로 트리거."""
    try:
        from worker.celery_app import app as celery_app

        celery_app.send_task(
            "worker.tasks.calculate_tension",
            queue="process",
        )
        return "calculate_tension 태스크 전송 완료 (비동기 실행 중)"
    except Exception as e:
        return f"calculate_tension 트리거 실패: {type(e).__name__}: {e}"


# ── Action: cleanup_redis_keys ────────────────────────────────────────────


async def _fix_cleanup_redis_keys(params: dict) -> str:
    """TTL이 -1인 영구 Redis 키 중 불필요한 것들을 정리."""
    redis = get_redis()
    deleted_count = 0
    scanned_count = 0

    # 정리 대상 패턴 (임시/캐시성 키)
    cleanup_patterns = ["rss:*", "anomaly:*", "health:pending:*"]
    # 절대 건드리면 안 되는 패턴
    protected_prefixes = [
        "tension:baseline:",
        "tension:history:",
        "celery",
    ]

    try:
        for pattern in cleanup_patterns:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=pattern, count=200
                )
                for key in keys:
                    scanned_count += 1
                    # bytes → str 변환
                    key_str = key if isinstance(key, str) else key.decode("utf-8")

                    # 보호 대상 스킵
                    if any(key_str.startswith(p) for p in protected_prefixes):
                        continue

                    # TTL 확인: -1이면 영구 키
                    ttl = await redis.ttl(key)
                    if ttl == -1:
                        await redis.delete(key)
                        deleted_count += 1

                if cursor == 0:
                    break

    except Exception as e:
        return f"Redis 키 정리 중 오류: {type(e).__name__}: {e} (스캔 {scanned_count}, 삭제 {deleted_count})"

    return f"Redis 키 정리 완료: 스캔 {scanned_count}개, 영구키 삭제 {deleted_count}개"


# ── Action: reprocess_orphans ─────────────────────────────────────────────


async def _fix_reprocess_orphans(params: dict) -> str:
    """클러스터 미할당 이벤트(오펀) 재처리를 Celery 태스크로 트리거."""
    try:
        from worker.celery_app import app as celery_app

        celery_app.send_task(
            "worker.tasks.reprocess_orphans",
            queue="process",
        )
        return "reprocess_orphans 태스크 전송 완료 (비동기 실행 중)"
    except Exception as e:
        return f"reprocess_orphans 트리거 실패: {type(e).__name__}: {e}"


# ── Action: retry_sns_publish ─────────────────────────────────────────────


async def _fix_retry_sns_publish(params: dict) -> str:
    """승인 후 30분 이상 미발행 상태인 SNS 포스트를 재발행 트리거."""
    try:
        async with AsyncSessionLocal() as db:
            # approved 상태이고 approved_at이 30분 이상 지난 포스트 조회
            stale_q = await db.execute(
                text("""
                    SELECT id, content_type, lang
                    FROM social_posts
                    WHERE status = 'approved'
                      AND approved_at IS NOT NULL
                      AND approved_at < NOW() - INTERVAL '30 minutes'
                """)
            )
            stale_posts = stale_q.fetchall()

            if not stale_posts:
                return "재발행 대상 SNS 포스트 없음"

            post_ids = [str(row.id) for row in stale_posts]

        # Celery 태스크로 발행 트리거
        try:
            from worker.celery_app import app as celery_app

            celery_app.send_task(
                "worker.tasks.publish_approved_social",
                queue="process",
            )
        except Exception as e:
            return f"publish 태스크 트리거 실패: {e} (대상 {len(post_ids)}건)"

        return f"SNS 재발행 트리거 완료: {len(post_ids)}건 (publish_approved_social 태스크 전송)"

    except Exception as e:
        if "does not exist" in str(e):
            return "social_posts 테이블 미발견"
        raise
