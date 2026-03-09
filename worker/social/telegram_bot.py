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

_RISK_EMOJI = {"low": "\U0001f7e2", "medium": "\U0001f7e1", "high": "\U0001f534"}
_CONTENT_TYPE_LABEL = {
    "daily_movers": "Daily Movers",
    "spike_alert": "Spike Alert",
    "weekly_recap": "Weekly Recap",
}


async def send_review_message(post: SocialPost) -> bool:
    """Telegram으로 플랫폼별 미리보기 + 요약 승인 메시지 전송."""
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.warning("Telegram 봇 설정 누락 (SOCIAL_TG_BOT_TOKEN / SOCIAL_TG_CHAT_ID)")
        return False

    try:
        import httpx
        from worker.social.adapters.x_adapter import _build_text as x_build_text
        from worker.social.adapters.threads_adapter import _build_text as threads_build_text
        from worker.social.config import (
            SOCIAL_PLATFORM_X_ENABLED,
            SOCIAL_PLATFORM_THREADS_ENABLED,
        )

        risk_emoji = _RISK_EMOJI.get(post.risk_level, "\u26aa")
        content_label = _CONTENT_TYPE_LABEL.get(post.content_type, post.content_type)
        hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
        post_id_str = str(post.id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. X 미리보기 메시지
            if SOCIAL_PLATFORM_X_ENABLED:
                x_text = x_build_text(post)
                x_msg = (
                    f"\U0001d54f [X] [{content_label}]\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"{x_text}\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"280\uc790 \uc911 {len(x_text)}\uc790 | Risk: {risk_emoji} {post.risk_level}"
                )
                x_keyboard = {
                    "inline_keyboard": [[
                        {"text": "\u2705 X \uc2b9\uc778", "callback_data": f"approve_x:{post_id_str}"},
                        {"text": "\u274c X \uac70\uc808", "callback_data": f"reject_x:{post_id_str}"},
                    ]]
                }
                await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": x_msg,
                        "reply_markup": x_keyboard,
                    },
                )

            # 2. Threads 미리보기 메시지
            if SOCIAL_PLATFORM_THREADS_ENABLED:
                threads_text = threads_build_text(post)
                threads_msg = (
                    f"\U0001f9f5 [Threads] [{content_label}]\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"{threads_text}\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                    f"500\uc790 \uc911 {len(threads_text)}\uc790 | Risk: {risk_emoji} {post.risk_level}"
                )
                threads_keyboard = {
                    "inline_keyboard": [[
                        {"text": "\u2705 Threads \uc2b9\uc778", "callback_data": f"approve_threads:{post_id_str}"},
                        {"text": "\u274c Threads \uac70\uc808", "callback_data": f"reject_threads:{post_id_str}"},
                    ]]
                }
                await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": threads_msg,
                        "reply_markup": threads_keyboard,
                    },
                )

            # 3. 요약 메시지 (항상) — 이미지 있으면 sendPhoto
            summary_text = (
                f"\U0001f4e2 [{content_label}] \uc2b9\uc778 \uc694\uccad\n"
                f"ID: {post_id_str}\n"
                f"{hashtag_str}"
            )
            summary_keyboard = {
                "inline_keyboard": [[
                    {"text": "\u2705 \uc804\uccb4 \uc2b9\uc778", "callback_data": f"approve_all:{post_id_str}"},
                    {"text": "\u270f\ufe0f \uc218\uc815", "callback_data": f"edit:{post_id_str}"},
                    {"text": "\u274c \uc804\uccb4 \uac70\uc808", "callback_data": f"reject:{post_id_str}"},
                ]]
            }

            image_sent = False
            if post.image_url:
                img_data = None
                if post.image_url.startswith("http"):
                    # Supabase 등 원격 URL → 다운로드
                    try:
                        dl_resp = await client.get(post.image_url, timeout=15.0)
                        if dl_resp.status_code == 200:
                            img_data = dl_resp.content
                    except Exception:
                        logger.warning("카드 이미지 다운로드 실패: %s", post.image_url)
                elif os.path.exists(post.image_url):
                    # 로컬 파일
                    with open(post.image_url, "rb") as f:
                        img_data = f.read()

                if img_data:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendPhoto",
                        data={
                            "chat_id": SOCIAL_TG_CHAT_ID,
                            "caption": summary_text,
                            "reply_markup": json.dumps(summary_keyboard, ensure_ascii=False),
                        },
                        files={"photo": ("card.png", img_data, "image/png")},
                    )
                    image_sent = True

            if not image_sent:
                resp = await client.post(
                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": SOCIAL_TG_CHAT_ID,
                        "text": summary_text,
                        "reply_markup": summary_keyboard,
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
    """Telegram 콜백 처리 — approve_all/approve_x/approve_threads/reject/reject_x/reject_threads/edit."""
    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        return "\uc798\ubabb\ub41c \ucf5c\ubc31 \ub370\uc774\ud130"

    action, post_id_str = parts

    try:
        post_id = uuid.UUID(post_id_str)
    except ValueError:
        return "\uc798\ubabb\ub41c \ud3ec\uc2a4\ud2b8 ID"

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(SocialPost).where(SocialPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if not post:
                return "\ud3ec\uc2a4\ud2b8\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4"

            # 하위호환: 기존 "approve" → "approve_all"
            if action in ("approve", "approve_all"):
                post.status = "approved"
                post.approved_at = datetime.now(timezone.utc)
                post.approved_by = username
                return "\u2705 \uc804\uccb4 \uc2b9\uc778 \uc644\ub8cc \u2014 \ub2e4\uc74c \ubc1c\ud589 \uc8fc\uae30\uc5d0 \uac8c\uc2dc\ub429\ub2c8\ub2e4"

            elif action == "approve_x":
                post.status = "approved"
                post.approved_at = datetime.now(timezone.utc)
                post.approved_by = username
                # Threads skipped
                existing = await db.execute(
                    select(SocialPostPlatform).where(
                        SocialPostPlatform.post_id == post.id,
                        SocialPostPlatform.platform == "threads",
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(SocialPostPlatform(
                        post_id=post.id,
                        platform="threads",
                        status="skipped",
                    ))
                return "\u2705 X\ub9cc \uc2b9\uc778 \uc644\ub8cc (Threads \uc2a4\ud0b5)"

            elif action == "approve_threads":
                post.status = "approved"
                post.approved_at = datetime.now(timezone.utc)
                post.approved_by = username
                # X skipped
                existing = await db.execute(
                    select(SocialPostPlatform).where(
                        SocialPostPlatform.post_id == post.id,
                        SocialPostPlatform.platform == "x",
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(SocialPostPlatform(
                        post_id=post.id,
                        platform="x",
                        status="skipped",
                    ))
                return "\u2705 Threads\ub9cc \uc2b9\uc778 \uc644\ub8cc (X \uc2a4\ud0b5)"

            elif action == "reject":
                post.status = "rejected"
                return "\u274c \uc804\uccb4 \uac70\uc808 \uc644\ub8cc"

            elif action == "reject_x":
                # X만 skipped 생성 (post 상태 유지)
                existing = await db.execute(
                    select(SocialPostPlatform).where(
                        SocialPostPlatform.post_id == post.id,
                        SocialPostPlatform.platform == "x",
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(SocialPostPlatform(
                        post_id=post.id,
                        platform="x",
                        status="skipped",
                    ))
                return "\u274c X \uac70\uc808 (Threads\ub294 \ubcc4\ub3c4 \uc2b9\uc778 \ud544\uc694)"

            elif action == "reject_threads":
                # Threads만 skipped 생성 (post 상태 유지)
                existing = await db.execute(
                    select(SocialPostPlatform).where(
                        SocialPostPlatform.post_id == post.id,
                        SocialPostPlatform.platform == "threads",
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(SocialPostPlatform(
                        post_id=post.id,
                        platform="threads",
                        status="skipped",
                    ))
                return "\u274c Threads \uac70\uc808 (X\ub294 \ubcc4\ub3c4 \uc2b9\uc778 \ud544\uc694)"

            elif action == "edit":
                return f"\u270f\ufe0f \uc218\uc815\ud560 \ud14d\uc2a4\ud2b8\ub97c \uc785\ub825\ud558\uc138\uc694 (post_id: {post_id})"

            return "\uc54c \uc218 \uc5c6\ub294 \uc561\uc158"


async def handle_edit_text(post_id: uuid.UUID, new_text: str) -> str:
    """포스트 본문 수정."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(SocialPost).where(SocialPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if not post:
                return "\ud3ec\uc2a4\ud2b8\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4"

            post.body_text = new_text[:500]
            post.status = "pending_review"
            return "\u270f\ufe0f \uc218\uc815 \uc644\ub8cc \u2014 \uc7ac\uc2b9\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4"


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
    # 수정 대기 중인 post_id 추적 {chat_id: (post_id, created_at)}
    edit_pending: dict[int, tuple[uuid.UUID, datetime]] = {}

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

                        # 헬스체크 승인 콜백 → health notifier로 위임
                        if cb_data.startswith("hfix:") or cb_data.startswith("hskip:"):
                            try:
                                from worker.health.notifier import _handle_health_callback
                                reply = await _handle_health_callback(client, cq, cb_data, username)
                            except Exception as e:
                                logger.warning("Health callback 처리 오류: %s", e)
                                reply = f"Health 처리 오류: {e}"
                            if chat_id:
                                await client.post(
                                    f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                                    json={"chat_id": chat_id, "text": reply},
                                )
                            continue

                        reply = await handle_callback(cb_data, username)

                        # edit 액션이면 대기 상태 등록
                        if cb_data.startswith("edit:"):
                            try:
                                pid = uuid.UUID(cb_data.split(":", 1)[1])
                                if chat_id:
                                    edit_pending[chat_id] = (pid, datetime.now(timezone.utc))
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
                            pid, _ = edit_pending.pop(chat_id)
                            reply = await handle_edit_text(pid, text)
                            await client.post(
                                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                                json={"chat_id": chat_id, "text": reply},
                            )
                        # 관리자 채팅의 일반 텍스트 → AI 에이전트
                        elif chat_id and str(chat_id) == SOCIAL_TG_CHAT_ID and text:
                            await _handle_agent_message(client, chat_id, text)

            # edit_pending TTL 정리: 10분 이상 된 엔트리 제거
            now = datetime.now(timezone.utc)
            expired = [cid for cid, (_, created) in edit_pending.items() if (now - created).total_seconds() > 600]
            for cid in expired:
                edit_pending.pop(cid, None)

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
            json={"chat_id": chat_id, "text": "\u26a0\ufe0f \ucc98\ub9ac \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4."},
        )


async def _sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
