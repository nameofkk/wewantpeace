"""X (Twitter) 어댑터 — tweepy v4+ OAuth 1.0a.

이미지 첨부: v1.1 media_upload(로컬파일) → v2 create_tweet(media_ids)
"""
import logging
import os

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")


def is_configured() -> bool:
    return bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_SECRET)


_CTA = "🔗 www.wewantpeace.live"


def _build_text(post: SocialPost) -> str:
    """본문 + 해시태그 + CTA 조합 (280자 제한)."""
    hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
    footer = f"\n{hashtag_str}\n{_CTA}" if hashtag_str else f"\n{_CTA}"
    full_text = post.body_text
    if len(full_text) + len(footer) <= 280:
        full_text = full_text + footer
    elif len(full_text) + len(f"\n{_CTA}") <= 280:
        # 해시태그 빼고 CTA만
        full_text = f"{full_text}\n{_CTA}"
    return full_text


def _upload_media(image_path: str) -> str | None:
    """로컬 이미지 파일 → tweepy v1.1 media_upload → media_id 반환."""
    try:
        import tweepy

        if not os.path.exists(image_path):
            logger.warning("이미지 파일 없음: %s", image_path)
            return None

        auth = tweepy.OAuth1UserHandler(
            X_API_KEY, X_API_SECRET,
            X_ACCESS_TOKEN, X_ACCESS_SECRET,
        )
        api = tweepy.API(auth)

        media = api.media_upload(filename=image_path)
        logger.info("미디어 업로드 완료: media_id=%s", media.media_id)

        # 업로드 완료 후 임시 파일 정리
        try:
            os.unlink(image_path)
        except Exception:
            pass

        return str(media.media_id)

    except Exception:
        logger.exception("미디어 업로드 실패")
        return None


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """X에 트윗 발행.

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

        # 이미지 첨부 (로컬 임시 파일 경로)
        media_ids = None
        if post.image_url and os.path.exists(post.image_url):
            media_id = _upload_media(post.image_url)
            if media_id:
                media_ids = [media_id]

        # 트윗 발행
        kwargs = {"text": full_text}
        if media_ids:
            kwargs["media_ids"] = media_ids

        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        logger.info("X 트윗 발행 완료: tweet_id=%s, post_id=%s", tweet_id, post.id)
        return tweet_id, None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("X 트윗 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
