"""텔레그램 알림 + 승인 처리.

헬스체크 결과를 텔레그램으로 전송하고, 인라인 키보드로 승인/무시를 받아
자동 수정을 실행합니다.
"""
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from backend.app.core.redis import get_redis

logger = logging.getLogger(__name__)

SOCIAL_TG_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
SOCIAL_TG_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")

# Redis 키 접두사
PENDING_PREFIX = "health:pending:"
APPROVAL_OFFSET_KEY = "health:tg_offset"
PENDING_TTL = 86400  # 24시간


# ── 알림 발송 ───────────────────────────────────────────────────────────────


async def send_health_report(results: list) -> bool:
    """헬스체크 결과를 텔레그램 메시지로 전송.

    자동 수정 가능한 이슈에는 인라인 키보드 버튼 추가.
    """
    from worker.health.checker import HealthCheckResult

    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.warning("텔레그램 봇 설정 누락 (SOCIAL_TG_BOT_TOKEN / SOCIAL_TG_CHAT_ID)")
        return False

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    redis = get_redis()

    # 이슈가 있는 체크와 정상 체크 분리
    all_issues = []
    lines = [f"\U0001f3e5 시스템 헬스체크 — {now}\n"]

    status_icons = {
        "ok": "\U0001f7e2",       # 녹색 원
        "warning": "\U0001f7e1",  # 노란 원
        "critical": "\U0001f534", # 빨간 원
    }

    for r in results:
        icon = status_icons.get(r.status, "\u2753")
        lines.append(f"{icon} {r.message}")

        for issue in r.issues:
            all_issues.append(issue)

    message = "\n".join(lines)

    # 이슈 없으면 간단 메시지만 전송
    if not all_issues:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": message,
                        "disable_web_page_preview": True,
                    },
                )
                if resp.status_code == 200:
                    logger.info("헬스체크 리포트 전송 완료 (이슈 없음)")
                    return True
                logger.error("헬스체크 리포트 전송 실패: %s", resp.text)
                return False
        except Exception:
            logger.exception("헬스체크 리포트 전송 오류")
            return False

    # 이슈 있는 경우: 인라인 키보드와 함께 전송
    # 먼저 메인 리포트 전송
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": SOCIAL_TG_CHAT_ID,
                    "text": message,
                },
            )
            if resp.status_code != 200:
                logger.error("헬스체크 리포트 전송 실패: %s", resp.text)
                return False

            # 각 이슈별로 승인 버튼 전송
            for issue in all_issues:
                if not issue.auto_fix_available:
                    continue

                # Redis에 pending action 저장
                action_data = {
                    "action": issue.fix_action,
                    "params": issue.fix_params,
                    "check_name": issue.check_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await redis.set(
                    f"{PENDING_PREFIX}{issue.action_id}",
                    json.dumps(action_data),
                    ex=PENDING_TTL,
                )

                # 수정 내용 설명
                fix_desc = _get_fix_description(issue.fix_action, issue.fix_params)

                # 인라인 키보드
                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "\u2705 승인",
                                "callback_data": f"hfix:{issue.action_id}",
                            },
                            {
                                "text": "\u274c 무시",
                                "callback_data": f"hskip:{issue.action_id}",
                            },
                        ]
                    ]
                }

                issue_msg = (
                    f"\U0001f527 수정 가능: {fix_desc}\n"
                    f"action: {issue.fix_action}"
                )

                await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": issue_msg,
                        "reply_markup": keyboard,
                        "disable_web_page_preview": True,
                    },
                )

            logger.info(
                "헬스체크 리포트 전송 완료 (이슈 %d개, 수정 가능 %d개)",
                len(all_issues),
                sum(1 for i in all_issues if i.auto_fix_available),
            )
            return True

    except Exception:
        logger.exception("헬스체크 리포트 전송 오류")
        return False


def _get_fix_description(action: str, params: dict) -> str:
    """수정 action에 대한 한국어 설명 생성."""
    if action == "reactivate_channels":
        ids = params.get("channel_ids", [])
        return f"{len(ids)}개 소스채널 재활성화"
    elif action == "reprocess_topics":
        return "미분류 이벤트 재분류 (reprocess)"
    elif action == "split_mega_cluster":
        ids = params.get("cluster_ids", [])
        return f"{len(ids)}개 메가 클러스터 분할"
    elif action == "reset_openai_rate_limit":
        return "OpenAI 에러 카운터 리셋"
    elif action == "cleanup_stale_fcm_tokens":
        return "만료된 FCM 토큰 정리"
    elif action == "expire_stale_subscriptions":
        return "만료 구독 상태 업데이트"
    elif action == "recalculate_tension":
        return "Tension Index 재계산"
    elif action == "cleanup_redis_keys":
        return "Redis 불필요 키 정리"
    elif action == "reprocess_orphans":
        return "오펀 이벤트 재클러스터링"
    elif action == "retry_sns_publish":
        return "미발행 SNS 포스트 재시도"
    elif action == "retry_spike_alerts":
        return "미전송 스파이크 알림 재발송"
    elif action == "data_quality_cleanup":
        return "데이터 품질 정리 (노이즈 재분류 + sev=0 비활성화 + 고아 정리)"
    return action


# ── 승인 처리 (Telegram getUpdates polling) ─────────────────────────────────


async def process_approvals() -> dict:
    """Telegram Bot API의 getUpdates로 callback_query를 확인하고 승인 처리.

    매 5분마다 Celery 태스크에서 호출됩니다.
    기존 telegram_bot.py의 polling과 충돌하지 않도록
    health 전용 callback_data 접두사(hfix:, hskip:)만 처리합니다.
    """
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        return {"status": "skipped", "reason": "bot not configured"}

    redis = get_redis()

    # 처리 건수 추적
    approved = 0
    skipped = 0
    errors = 0

    try:
        # 별도 offset 관리 — 기존 telegram_bot.py 폴링과 독립
        # 단, 기존 봇이 이미 getUpdates로 offset을 진행시키므로,
        # 여기서는 Redis에 저장된 pending action만 확인하는 방식으로 변경
        # → getUpdates 대신, 기존 봇의 polling에 health callback 핸들러를 등록하는 것이 더 안전
        #
        # 그러나 기존 봇이 hfix:/hskip: 콜백을 모르므로,
        # 여기서 짧은 timeout으로 별도 getUpdates를 수행합니다.
        # 기존 봇과 offset 충돌을 피하기 위해, 이 함수는 callback만 처리하고
        # offset을 전진시킵니다.

        offset_str = await redis.get(APPROVAL_OFFSET_KEY)
        offset = int(offset_str) if offset_str else 0

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 5,
                    "allowed_updates": '["callback_query"]',
                },
            )

            if resp.status_code != 200:
                logger.error("getUpdates 오류: %s", resp.text)
                return {"status": "error", "detail": resp.text}

            data = resp.json()
            updates = data.get("result", [])

            for update in updates:
                new_offset = update["update_id"] + 1
                await redis.set(APPROVAL_OFFSET_KEY, str(new_offset))

                if "callback_query" not in update:
                    continue

                cq = update["callback_query"]
                cb_data = cq.get("data", "")

                # health 전용 콜백만 처리
                if not cb_data.startswith("hfix:") and not cb_data.startswith("hskip:"):
                    continue

                action_type, action_id = cb_data.split(":", 1)
                from_user = cq.get("from", {})
                username = from_user.get("username", from_user.get("first_name", "unknown"))

                # Redis에서 pending action 조회
                pending_key = f"{PENDING_PREFIX}{action_id}"
                pending_data = await redis.get(pending_key)

                if not pending_data:
                    # 이미 처리됨 또는 만료
                    await _answer_callback(client, cq["id"], "이미 처리되었거나 만료됨")
                    continue

                action_info = json.loads(pending_data)

                if action_type == "hfix":
                    # 승인 → 수정 실행
                    try:
                        from worker.health.fixer import execute_fix
                        result_msg = await execute_fix(
                            action_info["action"],
                            action_info["params"],
                        )

                        # pending 삭제
                        await redis.delete(pending_key)
                        approved += 1

                        # 결과 알림
                        await _answer_callback(client, cq["id"], "승인됨 — 수정 실행 중")
                        await _send_fix_result(
                            client, username, action_info["action"], result_msg
                        )

                    except Exception as e:
                        errors += 1
                        logger.exception("수정 실행 오류: %s", e)
                        await _answer_callback(client, cq["id"], f"수정 오류: {e}")

                elif action_type == "hskip":
                    # 무시
                    await redis.delete(pending_key)
                    skipped += 1
                    await _answer_callback(client, cq["id"], "무시됨")
                    await client.post(
                        f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": SOCIAL_TG_CHAT_ID,
                            "text": f"\u274c {username}님이 {action_info['action']} 무시함",
                            "disable_web_page_preview": True,
                        },
                    )

    except Exception:
        logger.exception("승인 처리 오류")
        return {"status": "error", "approved": approved, "skipped": skipped}

    return {
        "status": "ok",
        "approved": approved,
        "skipped": skipped,
        "errors": errors,
    }


async def _answer_callback(client: httpx.AsyncClient, callback_id: str, text: str):
    """Telegram answerCallbackQuery."""
    try:
        await client.post(
            f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text[:200]},
        )
    except Exception:
        pass


async def _send_fix_result(
    client: httpx.AsyncClient,
    username: str,
    action: str,
    result_msg: str,
):
    """수정 결과를 텔레그램 채팅으로 전송."""
    try:
        text = (
            f"\u2705 자동 수정 완료\n"
            f"승인자: {username}\n"
            f"Action: {action}\n"
            f"결과: {result_msg[:500]}"
        )
        await client.post(
            f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": SOCIAL_TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
        )
    except Exception:
        logger.exception("수정 결과 알림 전송 오류")


# ── 기존 봇 polling에서 호출되는 health 콜백 핸들러 ─────────────────────────


async def _handle_health_callback(
    client: httpx.AsyncClient,
    cq: dict,
    cb_data: str,
    username: str,
) -> str:
    """기존 telegram_bot.py의 _poll_updates에서 hfix:/hskip: 콜백 시 호출.

    Returns:
        사용자에게 표시할 응답 텍스트.
    """
    redis = get_redis()
    action_type, action_id = cb_data.split(":", 1)

    pending_key = f"{PENDING_PREFIX}{action_id}"
    pending_data = await redis.get(pending_key)

    if not pending_data:
        await _answer_callback(client, cq["id"], "이미 처리되었거나 만료됨")
        return "이미 처리되었거나 만료된 요청입니다."

    action_info = json.loads(pending_data)

    if action_type == "hfix":
        # 승인 → 수정 실행
        try:
            from worker.health.fixer import execute_fix
            result_msg = await execute_fix(
                action_info["action"],
                action_info["params"],
            )
            await redis.delete(pending_key)
            await _answer_callback(client, cq["id"], "승인됨 — 수정 실행 중")
            await _send_fix_result(client, username, action_info["action"], result_msg)
            return f"\u2705 {action_info['action']} 수정 실행 완료: {result_msg[:300]}"
        except Exception as e:
            logger.exception("Health fix 실행 오류")
            await _answer_callback(client, cq["id"], f"수정 오류: {e}")
            return f"수정 실행 오류: {e}"

    elif action_type == "hskip":
        await redis.delete(pending_key)
        await _answer_callback(client, cq["id"], "무시됨")
        return f"\u274c {username}님이 {action_info['action']} 무시함"

    return "알 수 없는 action"
