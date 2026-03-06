"""Threads 어댑터 — Meta Graph API v21+ (PoC, 텍스트 전용)."""
import logging
import os
import time

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")

_GRAPH_API_BASE = "https://graph.threads.net/v1.0"


def is_configured() -> bool:
    return bool(THREADS_USER_ID and THREADS_ACCESS_TOKEN)


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """Threads에 포스트 발행 (2-step: create container → publish).

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "Threads API 키 미설정"

    try:
        import httpx

        hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
        full_text = post.body_text
        if hashtag_str:
            if len(full_text) + len(hashtag_str) + 1 <= 500:
                full_text = f"{full_text}\n{hashtag_str}"

        # Step 1: 미디어 컨테이너 생성
        with httpx.Client(timeout=15.0) as client:
            create_resp = client.post(
                f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
                params={
                    "media_type": "TEXT",
                    "text": full_text,
                    "access_token": THREADS_ACCESS_TOKEN,
                },
            )
            if create_resp.status_code != 200:
                return None, f"Container 생성 실패: {create_resp.text[:200]}"

            container_id = create_resp.json().get("id")
            if not container_id:
                return None, "Container ID 누락"

            # 컨테이너 처리 대기
            time.sleep(2)

            # Step 2: 발행
            publish_resp = client.post(
                f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads_publish",
                params={
                    "creation_id": container_id,
                    "access_token": THREADS_ACCESS_TOKEN,
                },
            )
            if publish_resp.status_code != 200:
                return None, f"Publish 실패: {publish_resp.text[:200]}"

            thread_id = publish_resp.json().get("id")
            logger.info("Threads 발행 완료: thread_id=%s, post_id=%s", thread_id, post.id)
            return str(thread_id), None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("Threads 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
