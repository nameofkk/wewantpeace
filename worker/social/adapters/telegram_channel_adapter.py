"""Telegram 채널 브로드캐스트 어댑터 — Bot API sendMessage/sendPhoto.

기존 telegram_bot.py는 커뮤니티 승인 봇 (관리자 검수/승인/거절).
이 파일은 공개 채널에 Daily Movers 등을 자동 포스팅하는 별도 브로드캐스트 어댑터.

Telegram 채널 최적화:
- HTML 포맷 (볼드/이탤릭/링크 지원)
- 이미지 + 캡션 조합이 engagement 2~3x
- 최대 4096자 (텍스트), 캡션 1024자
- 간결한 bilingual 뉴스 포맷
- 채널 구독자 알림 → 핵심만 전달
"""
import logging
import os
import re

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

TELEGRAM_BROADCAST_BOT_TOKEN = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
TELEGRAM_BROADCAST_CHANNEL_ID = os.getenv("TELEGRAM_BROADCAST_CHANNEL_ID", "")

_API_BASE = "https://api.telegram.org/bot"
_MAX_TEXT_LEN = 4096
_MAX_CAPTION_LEN = 1024


def is_configured() -> bool:
    return bool(TELEGRAM_BROADCAST_BOT_TOKEN and TELEGRAM_BROADCAST_CHANNEL_ID)


def _escape_html(text: str) -> str:
    """HTML parse mode용 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md_to_html(text: str) -> str:
    """마크다운 → Telegram HTML 변환 (이스케이프 전에 호출).

    **bold** → <b>bold</b>
    *italic* → <i>italic</i> (** 먼저 처리해야 단일 * 오작동 방지)
    __text__ → <u>text</u>
    나머지 마크다운 잔재는 strip.
    각 구간의 일반 텍스트는 HTML 이스케이프 적용.
    """
    import re as _re
    # bold: **text** → <b>text</b>  (이스케이프는 구간별로)
    parts = _re.split(r'\*\*(.+?)\*\*', text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # bold 구간
            result.append(f"<b>{_escape_html(part)}</b>")
        else:
            # italic: *text* (단독 *)
            sub_parts = _re.split(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', part)
            for j, sp in enumerate(sub_parts):
                if j % 2 == 1:
                    result.append(f"<i>{_escape_html(sp)}</i>")
                else:
                    # underline: __text__
                    u_parts = _re.split(r'__(.+?)__', sp)
                    for k, up in enumerate(u_parts):
                        if k % 2 == 1:
                            result.append(f"<u>{_escape_html(up)}</u>")
                        else:
                            result.append(_escape_html(up))
    return "".join(result)


def _build_text(post: SocialPost) -> str:
    """Telegram 채널용 HTML 본문 (4096자 한도).

    Telegram 전용 톤:
    - 뉴스 알림 스타일, 깔끔한 포맷
    - bilingual 원문 유지
    - 마크다운(**bold**) → HTML <b>bold</b> 자동 변환
    - 하단 CTA 링크
    """
    body = post.body_text

    # 기존 CTA/URL 정리 (해시태그는 Telegram 채널에서 유용하므로 유지)
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # 마크다운 → HTML 변환 (** → <b>, * → <i>) + HTML 이스케이프
    escaped_body = _md_to_html(body)

    # CTA (HTML 링크)
    cta = (
        "\n\n"
        '🌍 <a href="https://www.wewantpeace.live">WeWantPeace</a> · 실시간 분쟁 추적'
    )

    full_text = escaped_body + cta

    # 4096자 초과 시 잘라내기
    if len(full_text) > _MAX_TEXT_LEN:
        max_body = _MAX_TEXT_LEN - len(cta) - 10
        full_text = f"{escaped_body[:max_body]}...{cta}"

    return full_text


def _build_caption(post: SocialPost) -> str:
    """이미지 캡션용 축약 텍스트 (1024자 한도).

    sendPhoto의 caption은 1024자 제한이므로 본문을 요약.
    마크다운(**bold**) → HTML <b>bold</b> 자동 변환.
    """
    body = post.body_text

    # 정리
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # 마크다운 → HTML 변환 + 이스케이프
    escaped_body = _md_to_html(body)

    cta = (
        "\n\n"
        '🌍 <a href="https://www.wewantpeace.live">WeWantPeace</a>'
    )

    caption = escaped_body + cta

    if len(caption) > _MAX_CAPTION_LEN:
        max_body = _MAX_CAPTION_LEN - len(cta) - 10
        caption = f"{escaped_body[:max_body]}...{cta}"

    return caption


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """Telegram 공개 채널에 메시지 발행.

    이미지가 있으면 sendPhoto (캡션 포함), 없으면 sendMessage.

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "Telegram Broadcast 봇 미설정"

    try:
        import httpx

        api_base = f"{_API_BASE}{TELEGRAM_BROADCAST_BOT_TOKEN}"

        with httpx.Client(timeout=30.0) as client:
            # 이미지가 있으면 sendPhoto
            if post.image_url and post.image_url.startswith(("http://", "https://")):
                caption = _build_caption(post)
                resp = client.post(
                    f"{api_base}/sendPhoto",
                    json={
                        "chat_id": TELEGRAM_BROADCAST_CHANNEL_ID,
                        "photo": post.image_url,
                        "caption": caption,
                        "parse_mode": "HTML",
                    },
                )
            else:
                full_text = _build_text(post)
                resp = client.post(
                    f"{api_base}/sendMessage",
                    json={
                        "chat_id": TELEGRAM_BROADCAST_CHANNEL_ID,
                        "text": full_text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    },
                )

            if resp.status_code == 200:
                result = resp.json().get("result", {})
                message_id = str(result.get("message_id", ""))
                logger.info(
                    "Telegram 채널 발행 완료: message_id=%s, post_id=%s",
                    message_id, post.id,
                )
                return message_id, None
            else:
                error_detail = resp.text[:500]
                logger.error(
                    "Telegram 채널 발행 실패 [post=%s]: %s %s",
                    post.id, resp.status_code, error_detail,
                )
                return None, f"Telegram API {resp.status_code}: {error_detail}"

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("Telegram 채널 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
