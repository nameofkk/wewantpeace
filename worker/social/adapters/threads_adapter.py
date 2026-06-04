"""Threads 어댑터 — Meta Graph API v22.0 (텍스트 + 이미지).

Threads 2026 알고리즘 최적화:
- 500자 한도 (200~300자 최적 퍼포먼스)
- 대화형/커뮤니티 톤 (뉴스 속보 < 맥락 설명 + 의견)
- 답글(reply) > 좋아요 (13-20x 가치) → 질문으로 마무리
- 포스팅 후 30~90분이 결정적 (초기 engagement)
- 링크 페널티 없음 → URL 포함 가능
- 해시태그 적절히 사용 (검색 발견용)
- 홍보성 문구 ("좋아요 눌러주세요", "팔로우") 페널티
"""
import logging
import os
import re
import time

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")

_GRAPH_API_BASE = "https://graph.threads.net/v1.0"


def is_configured() -> bool:
    return bool(THREADS_USER_ID and THREADS_ACCESS_TOKEN)


# content_type별 맥락적 대화 유도 (generic 질문은 bait로 분류될 수 있음)
_ENGAGE_BY_TYPE = {
    "kscore_alert": [
        ("How will this affect the region?", "이 지역에 어떤 영향을 미칠까요?"),
        ("Is de-escalation still possible here?", "아직 상황 완화가 가능할까요?"),
        ("What's the bigger picture behind this?", "이 사건의 더 큰 맥락은 뭘까요?"),
    ],
    # 하위호환
    "spike_alert": [
        ("How will this affect the region?", "이 지역에 어떤 영향을 미칠까요?"),
        ("Is de-escalation still possible here?", "아직 상황 완화가 가능할까요?"),
        ("What's the bigger picture behind this?", "이 사건의 더 큰 맥락은 뭘까요?"),
    ],
    "daily_movers": [
        ("Which of these changes concerns you most?", "이 중 가장 우려되는 변화는?"),
        ("Any of these on your radar?", "이 중 주목하고 있던 이슈가 있나요?"),
        ("What pattern do you see here?", "어떤 패턴이 보이시나요?"),
    ],
    "weekly_recap": [
        ("What was the most significant development this week?", "이번 주 가장 중요한 변화는 뭐였을까요?"),
        ("Anything missing from this recap?", "이 요약에서 빠진 게 있나요?"),
        ("How does this week compare to the last?", "지난주와 비교하면 어떤가요?"),
    ],
}


def _build_text(post: SocialPost) -> str:
    """Threads 최적화 본문 (500자 한도).

    Threads 전용 톤:
    - 대화형, 맥락 있는 설명 (원문 전체 유지)
    - 대화 유도 질문으로 마무리
    - URL 포함 (프로필 유입)
    - 해시태그 없음 (Threads에서 불필요, 알고리즘 페널티 위험)
    """
    import hashlib

    body = post.body_text

    # 마크다운 방어적 제거 (AI가 가끔 ** 포함 → strip)
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)   # **bold** → bold
    body = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', body)  # *italic* → text
    body = re.sub(r'__(.+?)__', r'\1', body)         # __underline__ → text
    body = re.sub(r'_(.+?)_', r'\1', body)           # _italic_ → text

    # 기존 CTA/URL 라인 정리 (Threads 전용으로 교체)
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    # 해시태그 제거 (Threads에서 해시태그 없이 운영)
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # content_type에 맞는 맥락적 대화 유도 문구 (generic → 콘텐츠 연관)
    engage_list = _ENGAGE_BY_TYPE.get(post.content_type, _ENGAGE_BY_TYPE["kscore_alert"])
    idx = int(hashlib.md5(str(post.id).encode()).hexdigest(), 16) % len(engage_list)
    en_q, ko_q = engage_list[idx]
    engage = f"\n\n💬 {en_q}\n{ko_q}"

    # Threads CTA: 링크만 (해시태그 없음)
    link = "\n\n🔗 wewantpeace.live"

    full_text = body + engage + link

    # 500자 초과 시 잘라내기
    if len(full_text) > 500:
        max_body = 500 - len(engage) - len(link) - 3
        full_text = f"{body[:max_body]}...{engage}{link}"

    return full_text


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """Threads에 포스트 발행 (2-step: create container → publish).

    이미지: post.image_url이 http(s)로 시작하면 IMAGE 모드, 아니면 TEXT 모드.

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "Threads API 키 미설정"

    try:
        import httpx

        full_text = _build_text(post)

        # 이미지 URL 확인 — public URL이면 IMAGE 모드
        has_image = (
            post.image_url
            and post.image_url.startswith(("http://", "https://"))
        )

        # Step 1: 미디어 컨테이너 생성
        with httpx.Client(timeout=30.0) as client:
            params = {
                "text": full_text,
                "access_token": THREADS_ACCESS_TOKEN,
            }

            if has_image:
                params["media_type"] = "IMAGE"
                params["image_url"] = post.image_url
            else:
                params["media_type"] = "TEXT"

            create_resp = client.post(
                f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
                params=params,
            )
            if create_resp.status_code != 200:
                return None, f"Container 생성 실패: {create_resp.text[:200]}"

            container_id = create_resp.json().get("id")
            if not container_id:
                return None, "Container ID 누락"

            # 컨테이너 처리 대기 (이미지일 때 더 오래 대기)
            time.sleep(5 if has_image else 2)

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

            # v7: 댓글(reply) 자동 달기 — 이슈 링크 + 서비스 홍보
            if thread_id and post.source_cluster_id:
                try:
                    _post_reply(client, thread_id, post.source_cluster_id)
                except Exception as reply_err:
                    logger.warning("Threads 댓글 실패 (무시): %s", reply_err)

            return str(thread_id), None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("Threads 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg


def _post_reply(client, parent_thread_id: str, cluster_id) -> None:
    """v7: 메인 포스트에 링크+홍보 댓글 달기."""
    reply_text = (
        f"🔗 Full analysis: https://wewantpeace.live/issues/{cluster_id}\n"
        f"📡 Telegram: https://t.me/wewantpeace_live\n"
        f"📊 Real-time conflict tracking · WeWantPeace\n"
        f"상세 분석 보기 · 실시간 분쟁 모니터링"
    )

    # Step 1: reply container 생성
    create_resp = client.post(
        f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
        params={
            "media_type": "TEXT",
            "text": reply_text,
            "reply_to_id": parent_thread_id,
            "access_token": THREADS_ACCESS_TOKEN,
        },
    )
    if create_resp.status_code != 200:
        logger.warning("Reply container 실패: %s", create_resp.text[:200])
        return

    container_id = create_resp.json().get("id")
    if not container_id:
        return

    time.sleep(2)

    # Step 2: publish reply
    publish_resp = client.post(
        f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        },
    )
    if publish_resp.status_code == 200:
        reply_id = publish_resp.json().get("id")
        logger.info("Threads 댓글 발행: reply_id=%s, parent=%s", reply_id, parent_thread_id)
    else:
        logger.warning("Reply publish 실패: %s", publish_resp.text[:200])
