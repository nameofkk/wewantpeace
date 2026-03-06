"""X (Twitter) 어댑터 — tweepy v4+ OAuth 1.0a."""
import logging
import os
from datetime import datetime, timezone

from backend.app.models.social_post import SocialPost, SocialPostPlatform

logger = logging.getLogger(__name__)

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")


def is_configured() -> bool:
    return bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_SECRET)


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

        # 본문 + 해시태그 조합
        hashtag_str = " ".join(post.hashtags) if post.hashtags else ""
        full_text = post.body_text
        if hashtag_str:
            # 280자 제한 고려
            if len(full_text) + len(hashtag_str) + 1 <= 280:
                full_text = f"{full_text}\n{hashtag_str}"

        response = client.create_tweet(text=full_text)
        tweet_id = str(response.data["id"])
        logger.info("X 트윗 발행 완료: tweet_id=%s, post_id=%s", tweet_id, post.id)
        return tweet_id, None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("X 트윗 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
