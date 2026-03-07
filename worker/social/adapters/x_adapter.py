"""X (Twitter) 어댑터 — tweepy v4+ OAuth 1.0a.

X 2026 알고리즘 최적화:
- Grok이 본문을 직접 읽음 → 해시태그 불필요 (과다 사용 시 페널티)
- 비프리미엄 계정 링크 포스트 노출 0 → URL 제거, 브랜드명만
- 네이티브 이미지 = 10x 더 높은 인게이지먼트
- 초기 6시간 내 engagement가 핵심 (6시간마다 점수 절반 감소)
- 간결하고 임팩트 있는 뉴스 헤드라인 스타일 (70~100자 최적)
- 리플/RT 유도 > 좋아요 (13-20x 가치)

이미지 첨부: v1.1 media_upload(로컬파일) → v2 create_tweet(media_ids)
"""
import logging
import os
import re

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")


def is_configured() -> bool:
    return bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_SECRET)


_CTA = "— WeWantPeace · 실시간 분쟁 추적"


def _build_text(post: SocialPost) -> str:
    """X 최적화 본문 조합 (280자 제한).

    X 전용 톤:
    - 뉴스 속보 스타일, 짧고 강렬
    - bilingual → 각 언어 첫 문장만 (간결)
    - URL 완전 제거 (비프리미엄 페널티)
    - 해시태그 사용 안 함 (Grok이 직접 분류, 과다 시 페널티)
    - 브랜드명 CTA만 (프로필 링크로 유도)
    """
    body = post.body_text

    # URL, CTA 라인, 해시태그 제거
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # X 톤: 헤드라인 스타일 — 각 언어 첫 문장만 추출
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    en_lines = []
    ko_lines = []
    for line in lines:
        cleaned = re.sub(r'^[🚨⚡🔴🟡🟢⚪📊📈]+\s*', '', line).strip()
        if not cleaned:
            continue
        # 한국어 포함 여부로 분류
        if re.search(r'[\uac00-\ud7a3]', cleaned):
            ko_lines.append(cleaned)
        else:
            en_lines.append(cleaned)

    # 첫 문장씩만 사용 (헤드라인 스타일)
    en_head = en_lines[0] if en_lines else ""
    ko_head = ko_lines[0] if ko_lines else ""

    if en_head and ko_head:
        body = f"🚨 {en_head}\n{ko_head}"
    elif en_head:
        body = f"🚨 {en_head}"
    elif ko_head:
        body = f"🚨 {ko_head}"

    footer = f"\n\n{_CTA}"

    if len(body) + len(footer) <= 280:
        return body + footer

    # 본문이 길면 잘라서 맞춤
    max_body = 280 - len(footer) - 3
    return f"{body[:max_body]}...\n\n{_CTA}"


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
