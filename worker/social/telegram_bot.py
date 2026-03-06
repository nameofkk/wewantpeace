"""SNS Telegram 승인 봇 — 콘텐츠 검수 및 승인/거절 처리 + AI 에이전트."""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.social_post import SocialPost, SocialPostPlatform

logger = logging.getLogger(__name__)

SOCIAL_TG_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
SOCIAL_TG_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")

_RISK_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴"}
_CONTENT_TYPE_LABEL = {
    "daily_movers": "Daily Movers",
    "spike_alert": "Spike Alert",
    "weekly_recap": "Weekly Recap",
}


async def send_review_message(post: SocialPost) -> bool:
    """Telegram으로 승인 요청 메시지 전송."""
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.warning("Telegram 봇 설정 누락 (SOCIAL_TG_BOT_TOKEN / SOCIAL_TG_CHAT_ID)")
        return False

    try:
        import httpx

        risk_emoji = _RISK_EMOJI.get(post.risk_level, "⚪")
        content_label = _CONTENT_TYPE_LABEL.get(post.content_type, post.content_type)
        hashtag_str = " ".join(post.hashtags) if post.hashtags else ""

        text = (
            f"📢 [{content_label}]\n"
            f"──────────\n"
            f"{post.body_text}\n"
            f"──────────\n"
            f"{hashtag_str}\n\n"
            f"Risk: {risk_emoji} {post.risk_level} | Lang: {post.lang}\n"
            f"ID: {post.id}"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ 승인", "callback_data": f"approve:{post.id}"},
                    {"text": "✏️ 수정", "callback_data": f"edit:{post.id}"},
                    {"text": "❌ 거절", "callback_data": f"reject:{post.id}"},
                ]
            ]
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 카드 이미지가 있으면 sendPhoto, 없으면 sendMessage
            if post.image_url and os.path.exists(post.image_url):
                with open(post.image_url, "rb") as img_file:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendPhoto",
                        data={
                            "chat_id": SOCIAL_TG_CHAT_ID,
                            "caption": text,
                            "reply_markup": json.dumps(keyboard),
                        },
                        files={"photo": ("card.png", img_file, "image/png")},
                    )
            else:
                resp = await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": text,
                        "reply_markup": keyboard,
                    },
                )
            if resp.status_code == 200:
                logger.info("Telegram 승인 메시지 전송 완료: post=%s", post.id)
                return True
            else:
                logger.error("Telegram API 오류: %s %s", resp.status_code, resp.text)
                return False

    except Exception:
        logger.exception("Telegram 메시지 전송 실패")
        return False


async def handle_callback(callback_data: str, username: str) -> str:
    """Telegram 콜백 처리 — approve/reject/edit."""
    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        return "잘못된 콜백 데이터"

    action, post_id_str = parts

    try:
        post_id = uuid.UUID(post_id_str)
    except ValueError:
        return "잘못된 포스트 ID"

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(SocialPost).where(SocialPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if not post:
                return "포스트를 찾을 수 없습니다"

            if action == "approve":
                post.status = "approved"
                post.approved_at = datetime.now(timezone.utc)
                post.approved_by = username
                return f"✅ 승인 완료 — 다음 발행 주기에 게시됩니다"

            elif action == "reject":
                post.status = "rejected"
                return f"❌ 거절 완료"

            elif action == "edit":
                return f"✏️ 수정할 텍스트를 입력하세요 (post_id: {post_id})"

            return "알 수 없는 액션"


async def handle_edit_text(post_id: uuid.UUID, new_text: str) -> str:
    """포스트 본문 수정."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(SocialPost).where(SocialPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if not post:
                return "포스트를 찾을 수 없습니다"

            post.body_text = new_text[:280]
            post.status = "pending_review"
            return f"✏️ 수정 완료 — 재승인이 필요합니다"


def start_polling_loop():
    """Celery worker_ready 시그널로 시작할 polling loop.

    별도 스레드에서 실행되어 Telegram 업데이트를 폴링합니다.
    """
    import asyncio
    import threading

    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.info("Telegram 봇 미설정, polling 건너뜀")
        return

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_poll_updates())

    thread = threading.Thread(target=_run, daemon=True, name="social-tg-bot")
    thread.start()
    logger.info("Telegram 봇 polling 스레드 시작")


async def _poll_updates():
    """Telegram Bot API long polling."""
    import httpx

    offset = 0
    # 수정 대기 중인 post_id 추적 {chat_id: post_id}
    edit_pending: dict[int, uuid.UUID] = {}

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                if resp.status_code != 200:
                    logger.error("Telegram getUpdates 오류: %s", resp.text)
                    await _sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # 콜백 쿼리 처리
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        cb_data = cq.get("data", "")
                        from_user = cq.get("from", {})
                        username = from_user.get("username", from_user.get("first_name", "unknown"))
                        chat_id = cq.get("message", {}).get("chat", {}).get("id")

                        reply = await handle_callback(cb_data, username)

                        # edit 액션이면 대기 상태 등록
                        if cb_data.startswith("edit:"):
                            try:
                                pid = uuid.UUID(cb_data.split(":", 1)[1])
                                if chat_id:
                                    edit_pending[chat_id] = pid
                            except ValueError:
                                pass

                        # 콜백 응답
                        await client.post(
                            f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/answerCallbackQuery",
                            json={"callback_query_id": cq["id"], "text": reply[:200]},
                        )
                        # 채팅에도 메시지 전송
                        if chat_id:
                            await client.post(
                                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply},
                            )

                    # 텍스트 메시지 처리 (수정 대기 중인 경우)
                    elif "message" in update:
                        msg = update["message"]
                        chat_id = msg.get("chat", {}).get("id")
                        text = msg.get("text", "")

                        if chat_id and chat_id in edit_pending and text:
                            pid = edit_pending.pop(chat_id)
                            reply = await handle_edit_text(pid, text)
                            await client.post(
                                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply},
                            )
                        # 관리자 채팅의 일반 텍스트 → AI 에이전트
                        elif chat_id and str(chat_id) == SOCIAL_TG_CHAT_ID and text:
                            await _handle_agent_message(client, chat_id, text)

        except Exception:
            logger.exception("Telegram polling 오류")
            await _sleep(5)


async def _handle_agent_message(client, chat_id: int, text: str):
    """관리자 채팅에서 온 일반 텍스트를 AI 에이전트로 처리."""
    from worker.social.monitor import handle_ai_question, handle_status_command

    try:
        # /status 명령어
        if text.strip().lower() == "/status":
            reply = await handle_status_command()
        else:
            # 타이핑 표시
            await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )
            reply = await handle_ai_question(text)

        # 4096자 초과 시 분할 전송
        for i in range(0, len(reply), 4096):
            chunk = reply[i:i + 4096]
            await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": chunk},
            )
    except Exception:
        logger.exception("AI 에이전트 메시지 처리 오류")
        await client.post(
            f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": "⚠️ 처리 중 오류가 발생했습니다."},
        )


async def _sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
