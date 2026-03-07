"""Telegram 채널 브로드캐스트 어댑터 — Bot API sendMessage/sendPhoto.

기존 telegram_bot.py는 커뮤니티 승인 봇 (관리자 검수/승인/거절).
이 파일은 공개 채널에 Daily Movers 등을 자동 포스팅하는 별도 브로드캐스트 어댑터.

Telegram 채널 최적화:
- MarkdownV2 포맷 (볼드/이탤릭/링크 지원)
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


def _escape_markdown_v2(text: str) -> str:
    """MarkdownV2에서 이스케이프가 필요한 특수문자 처리.

    이스케이프 대상: _ * [ ] ( ) ~ ` > # + - = | { } . !
    단, 이미 의도적으로 사용한 마크다운 문법은 보존해야 하므로
    bold(**) 등을 먼저 변환 후 나머지를 이스케이프.
    """
    # 보존할 마크다운: *bold*, _italic_ → 먼저 플레이스홀더로 치환
    # 실제로는 plain text를 이스케이프하는 용도이므로 전부 이스케이프
    special_chars = r'_*[]()~`>#+-=|{}.!'
    escaped = text
    for ch in special_chars:
        escaped = escaped.replace(ch, f'\\{ch}')
    return escaped


def _build_text(post: SocialPost) -> str:
    """Telegram 채널용 MarkdownV2 본문 (4096자 한도).

    Telegram 전용 톤:
    - 뉴스 알림 스타일, 깔끔한 포맷
    - bilingual 원문 유지
    - 볼드 헤드라인 + 일반 본문
    - 하단 CTA 링크
    """
    body = post.body_text

    # 기존 CTA/URL/해시태그 정리
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # MarkdownV2 이스케이프
    escaped_body = _escape_markdown_v2(body)

    # 해시태그 (이스케이프)
    hashtag_str = ""
    if post.hashtags:
        raw_tags = " ".join(post.hashtags[:5])
        hashtag_str = _escape_markdown_v2(raw_tags)

    # CTA (MarkdownV2 링크 문법)
    cta = (
        "\n\n"
        "\\-\\-\\-\n"
        "🌍 [WeWantPeace \\- Live Tracker](https://www.wewantpeace.live)\n"
        "실시간 분쟁 추적"
    )

    full_text = escaped_body + cta
    if hashtag_str:
        full_text = f"{full_text}\n\n{hashtag_str}"

    # 4096자 초과 시 잘라내기
    if len(full_text) > _MAX_TEXT_LEN:
        max_body = _MAX_TEXT_LEN - len(cta) - 10
        full_text = f"{escaped_body[:max_body]}\\.\\.\\.\n{cta}"

    return full_text


def _build_caption(post: SocialPost) -> str:
    """이미지 캡션용 축약 텍스트 (1024자 한도).

    sendPhoto의 caption은 1024자 제한이므로 본문을 요약.
    """
    body = post.body_text

    # 정리
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    escaped_body = _escape_markdown_v2(body)

    cta = (
        "\n\n"
        "🌍 [WeWantPeace](https://www.wewantpeace.live)"
    )

    caption = escaped_body + cta

    if len(caption) > _MAX_CAPTION_LEN:
        max_body = _MAX_CAPTION_LEN - len(cta) - 10
        caption = f"{escaped_body[:max_body]}\\.\\.\\.\n{cta}"

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
                        "parse_mode": "MarkdownV2",
                    },
                )
            else:
                full_text = _build_text(post)
                resp = client.post(
                    f"{api_base}/sendMessage",
                    json={
                        "chat_id": TELEGRAM_BROADCAST_CHANNEL_ID,
                        "text": full_text,
                        "parse_mode": "MarkdownV2",
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
