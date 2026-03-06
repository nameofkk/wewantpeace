"""Instagram 어댑터 — Meta Graph API v22.0.

이미지 필수 플랫폼: post.image_url이 public URL이 아니면 스킵.
2-step 패턴: 컨테이너 생성 → status 폴링 → 발행.
"""
import logging
import os
import time

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

_GRAPH_API_BASE = "https://graph.instagram.com/v22.0"

_MAX_CAPTION_LEN = 2200


def is_configured() -> bool:
    return bool(INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN)


def _build_caption(post: SocialPost) -> str:
    """본문 + CTA + 해시태그 조합 (2200자 제한)."""
    caption = post.body_text

    # CTA 추가
    if "wewantpeace" not in caption.lower():
        caption = f"{caption}\n\n🌍 More updates → link in bio\n실시간 분석 → 프로필 링크"

    hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
    if hashtag_str:
        candidate = f"{caption}\n\n{hashtag_str}"
        if len(candidate) <= _MAX_CAPTION_LEN:
            caption = candidate
    return caption[:_MAX_CAPTION_LEN]


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """Instagram에 이미지 포스트 발행.

    Instagram은 이미지 필수 — public URL이 아니면 스킵.

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "Instagram API 키 미설정"

    # Instagram은 이미지 필수
    if not post.image_url or not post.image_url.startswith(("http://", "https://")):
        return None, "Instagram은 public 이미지 URL 필수 — 스킵"

    try:
        import httpx

        caption = _build_caption(post)

        with httpx.Client(timeout=60.0) as client:
            # Step 1: 미디어 컨테이너 생성
            create_resp = client.post(
                f"{_GRAPH_API_BASE}/{INSTAGRAM_USER_ID}/media",
                params={
                    "image_url": post.image_url,
                    "caption": caption,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
            )
            if create_resp.status_code != 200:
                return None, f"Container 생성 실패: {create_resp.text[:200]}"

            container_id = create_resp.json().get("id")
            if not container_id:
                return None, "Container ID 누락"

            # Step 2: 컨테이너 status 폴링 (FINISHED 될 때까지, 최대 30초)
            for _ in range(6):
                time.sleep(5)
                status_resp = client.get(
                    f"{_GRAPH_API_BASE}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": INSTAGRAM_ACCESS_TOKEN,
                    },
                )
                if status_resp.status_code == 200:
                    status_code = status_resp.json().get("status_code")
                    if status_code == "FINISHED":
                        break
                    if status_code == "ERROR":
                        return None, f"Container 처리 실패: {status_resp.text[:200]}"

            # Step 3: 발행
            publish_resp = client.post(
                f"{_GRAPH_API_BASE}/{INSTAGRAM_USER_ID}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
            )
            if publish_resp.status_code != 200:
                return None, f"Publish 실패: {publish_resp.text[:200]}"

            media_id = publish_resp.json().get("id")
            logger.info("Instagram 발행 완료: media_id=%s, post_id=%s", media_id, post.id)
            return str(media_id), None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("Instagram 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
