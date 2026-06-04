"""X (Twitter) 어댑터 — tweepy v4+ OAuth 1.0a.

X 2026 알고리즘 최적화:
- 해시태그 1-2개 사용 → 리트윗 확률 +33% (3개 이상은 역효과 -17%)
- 링크는 본문이 아닌 첫 번째 답글에 → 본문 노출 극대화
- 네이티브 이미지 = 10x 더 높은 인게이지먼트
- 초기 6시간 내 engagement가 핵심 (6시간마다 점수 절반 감소)
- 간결하고 임팩트 있는 뉴스 헤드라인 스타일 (70~100자 최적)
- 리플/RT 유도 > 좋아요 (13-20x 가치)
- 커뮤니티 게시 = 전체 사용자 노출 (2026~)

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

# 토픽 → 해시태그 매핑 (국가 해시태그와 조합하여 1-2개 선택)
_TOPIC_HASHTAGS: dict[str, str] = {
    "conflict": "#OSINT",
    "terror": "#Security",
    "coup": "#Geopolitics",
    "sanctions": "#Geopolitics",
    "cyber": "#Cybersecurity",
    "protest": "#WorldNews",
    "diplomacy": "#Geopolitics",
    "maritime": "#Security",
    "disaster": "#BreakingNews",
    "health": "#GlobalHealth",
}


def _pick_hashtags(post: SocialPost, max_tags: int = 2) -> str:
    """토픽 + 국가 기반으로 해시태그 1-2개 선택.

    3개 이상 사용 시 인게이지먼트 -17% → 최대 2개로 제한.
    """
    tags: list[str] = []

    # 1) DB에 저장된 해시태그에서 국가 태그 우선 사용 (#WeWantPeace 제외)
    if post.hashtags:
        for t in post.hashtags:
            if t != "#WeWantPeace" and t not in tags:
                tags.append(t)
                if len(tags) >= max_tags:
                    break

    # 2) 부족하면 토픽 해시태그 추가
    if len(tags) < max_tags and hasattr(post, "content_type"):
        # source_cluster에서 topic 추출 시도
        topic_tag = None
        body = post.body_text or ""
        for topic, tag in _TOPIC_HASHTAGS.items():
            if topic.lower() in body.lower():
                topic_tag = tag
                break
        if topic_tag and topic_tag not in tags:
            tags.append(topic_tag)

    # 3) 여전히 0개면 범용 태그
    if not tags:
        tags.append("#OSINT")

    return " ".join(tags[:max_tags])


def _build_text(post: SocialPost) -> str:
    """X 최적화 본문 조합 (280자 제한).

    X 전용 톤:
    - 뉴스 속보 스타일, 짧고 강렬
    - bilingual → 각 언어 첫 문장만 (간결)
    - URL 제거 (첫 답글에서 별도 게시)
    - 해시태그 1-2개 자동 추가 (토픽+국가 기반)
    - 브랜드명 CTA
    """
    body = post.body_text

    # 마크다운 제거
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', body)
    body = re.sub(r'__(.+?)__', r'\1', body)
    body = re.sub(r'_(.+?)_', r'\1', body)

    # URL, CTA 라인, 기존 해시태그 제거 (새로 추가할 것이므로)
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

    # 해시태그 1-2개 추가
    hashtag_str = _pick_hashtags(post)
    footer = f"\n\n{hashtag_str}\n\n{_CTA}"

    if len(body) + len(footer) <= 280:
        return body + footer

    # 본문이 길면 잘라서 맞춤
    max_body = 280 - len(footer) - 3
    return f"{body[:max_body]}...\n\n{hashtag_str}\n\n{_CTA}"


def _download_to_temp(url: str) -> str | None:
    """URL 이미지를 로컬 임시 파일로 다운로드."""
    try:
        import tempfile
        import httpx
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("이미지 다운로드 실패 [%s]: %s", resp.status_code, url[:80])
                return None
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
    except Exception:
        logger.warning("이미지 다운로드 오류: %s", url[:80])
        return None


def _upload_media(image_source: str) -> str | None:
    """이미지 → tweepy v1.1 media_upload → media_id 반환.

    image_source: 로컬 경로 또는 http(s) URL
    """
    try:
        import tweepy

        # URL이면 먼저 로컬로 다운로드
        if image_source.startswith(("http://", "https://")):
            local_path = _download_to_temp(image_source)
            if not local_path:
                return None
            is_temp = True
        else:
            local_path = image_source
            is_temp = False

        if not os.path.exists(local_path):
            logger.warning("이미지 파일 없음: %s", local_path)
            return None

        auth = tweepy.OAuth1UserHandler(
            X_API_KEY, X_API_SECRET,
            X_ACCESS_TOKEN, X_ACCESS_SECRET,
        )
        api = tweepy.API(auth)

        media = api.media_upload(filename=local_path)
        logger.info("미디어 업로드 완료: media_id=%s", media.media_id)

        # 업로드 완료 후 임시 파일 정리
        if is_temp:
            try:
                os.unlink(local_path)
            except Exception:
                pass

        return str(media.media_id)

    except Exception:
        logger.exception("미디어 업로드 실패")
        return None


def _build_reply_text(post: SocialPost) -> str | None:
    """소스 링크를 포함한 답글 텍스트 생성.

    링크는 본문이 아닌 첫 번째 답글에 게시해야 노출 페널티 없음.
    클러스터 ID가 있으면 이슈 상세 링크, 없으면 메인 링크.
    클릭 유도 문구 포함.
    """
    base_url = "https://www.wewantpeace.live"

    tg = "https://t.me/wewantpeace_live"

    if post.source_cluster_id:
        link = f"{base_url}/issues/{post.source_cluster_id}?lang=en"
        return (
            "📊 Full timeline · sources · severity breakdown\n"
            "타임라인 · 출처 · 심각도 분석 보기\n\n"
            f"🔗 {link}\n"
            f"📡 Telegram: {tg}\n\n"
            "🆓 Free · 195 countries · Updated every 3 min"
        )

    return (
        "🌐 Real-time conflict monitoring across 195 countries\n"
        "195개국 분쟁 상황 실시간 모니터링\n\n"
        f"🔗 {base_url}\n"
        f"📡 Telegram: {tg}\n\n"
        "🆓 Free · No signup required"
    )


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """X에 트윗 발행 + 소스 링크 답글.

    1. 메인 트윗: 헤드라인 + 해시태그 + 이미지 (링크 없음 → 노출 극대화)
    2. 첫 답글: 소스 링크 (답글에 링크 → 페널티 없음)

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "X API 키 미설정"

    import time
    # 402(크레딧 소진)는 재시도 무의미 → 즉시 실패 처리
    _RETRYABLE_CODES = ("403", "429")
    _MAX_RETRIES = 2

    for attempt in range(_MAX_RETRIES + 1):
        try:
            import tweepy

            client = tweepy.Client(
                consumer_key=X_API_KEY,
                consumer_secret=X_API_SECRET,
                access_token=X_ACCESS_TOKEN,
                access_token_secret=X_ACCESS_SECRET,
            )

            full_text = _build_text(post)

            # 이미지 첨부 (로컬 경로 또는 Supabase URL)
            media_ids = None
            if post.image_url:
                media_id = _upload_media(post.image_url)
                if media_id:
                    media_ids = [media_id]

            # 메인 트윗 발행 (링크 없음)
            kwargs = {"text": full_text}
            if media_ids:
                kwargs["media_ids"] = media_ids

            response = client.create_tweet(**kwargs)
            tweet_id = str(response.data["id"])
            logger.info("X 트윗 발행 완료: tweet_id=%s, post_id=%s", tweet_id, post.id)

            # 첫 번째 답글로 소스 링크 게시
            reply_text = _build_reply_text(post)
            if reply_text:
                try:
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet_id,
                    )
                    logger.info("X 링크 답글 게시 완료: parent=%s", tweet_id)
                except Exception as reply_err:
                    # 답글 실패해도 메인 트윗은 성공으로 처리
                    logger.warning("X 링크 답글 실패 (무시): %s", str(reply_err)[:200])

            return tweet_id, None

        except Exception as e:
            error_msg = str(e)[:500]
            # 403/429는 재시도 가치 있음 (rate limit 일시 오류)
            if attempt < _MAX_RETRIES and any(code in error_msg for code in _RETRYABLE_CODES):
                wait = (attempt + 1) * 30
                logger.warning("X 트윗 발행 재시도 [%d/%d] %ds 후: %s", attempt + 1, _MAX_RETRIES, wait, error_msg)
                time.sleep(wait)
                continue
            logger.error("X 트윗 발행 실패 [post=%s]: %s", post.id, error_msg)
            return None, error_msg
