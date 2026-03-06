"""X (Twitter) 어댑터 — tweepy v4+ OAuth 1.0a.

이미지 첨부: v1.1 media_upload → v2 create_tweet(media_ids)
Thread 지원: in_reply_to_tweet_id 로 ko reply 연결
"""
import logging
import os
import tempfile
from urllib.request import urlretrieve

from backend.app.models.social_post import SocialPost, SocialPostPlatform

logger = logging.getLogger(__name__)

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")


def is_configured() -> bool:
    return bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_SECRET)


def _build_text(post: SocialPost) -> str:
    """본문 + 해시태그 조합 (280자 제한)."""
    hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
    full_text = post.body_text
    if hashtag_str:
        if len(full_text) + len(hashtag_str) + 1 <= 280:
            full_text = f"{full_text}\n{hashtag_str}"
    return full_text


def _upload_media(image_url: str) -> str | None:
    """이미지 URL → tweepy v1.1 media_upload → media_id 반환."""
    try:
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            X_API_KEY, X_API_SECRET,
            X_ACCESS_TOKEN, X_ACCESS_SECRET,
        )
        api = tweepy.API(auth)

        # 이미지 다운로드 → 임시 파일
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
            urlretrieve(image_url, tmp_path)

        media = api.media_upload(filename=tmp_path)
        os.unlink(tmp_path)
        logger.info("미디어 업로드 완료: media_id=%s", media.media_id)
        return str(media.media_id)

    except Exception:
        logger.exception("미디어 업로드 실패")
        # 임시 파일 정리
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None


def publish(
    post: SocialPost,
    reply_to_tweet_id: str | None = None,
) -> tuple[str | None, str | None]:
    """X에 트윗 발행.

    Args:
        post: 발행할 소셜 포스트
        reply_to_tweet_id: 이 트윗에 대한 reply로 발행 (Thread 연결)

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "X API 키 미설정"

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )

        full_text = _build_text(post)

        # 이미지 첨부
        media_ids = None
        if post.image_url:
            media_id = _upload_media(post.image_url)
            if media_id:
                media_ids = [media_id]

        # 트윗 발행
        kwargs = {"text": full_text}
        if media_ids:
            kwargs["media_ids"] = media_ids
        if reply_to_tweet_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_tweet_id

        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        logger.info(
            "X 트윗 발행 완료: tweet_id=%s, post_id=%s, reply_to=%s",
            tweet_id, post.id, reply_to_tweet_id,
        )
        return tweet_id, None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("X 트윗 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
