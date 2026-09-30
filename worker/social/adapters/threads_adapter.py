"""Threads 어댑터 — Meta Graph API (텍스트 + 이미지).

2026-09-30 개편 (영어 정보형 브리프):
- 본문은 생성기가 완성해서 넘긴다. 여기서는 마크다운·이모지만 걷고 500자로 자른다.
  예전처럼 이모지 질문("💬 How will this affect...")·"🔗 wewantpeace.live" 를 덧붙이지 않는다.
- 주제 태그는 본문 해시태그 대신 topic_tag 파라미터 1개 (post.hashtags[0]).
- 게시 직후 댓글은 출처 목록(post.reply_text). 텔레그램 링크·한국어 홍보 문구는 뺐다.
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


def _build_text(post: SocialPost) -> str:
    """게시 본문 (500자). 링크는 남긴다 — 2026 기준 링크 불이익 없음."""
    from worker.social.brief import strip_emoji

    body = post.body_text or ""
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    body = re.sub(r"__(.+?)__", r"\1", body)
    body = strip_emoji(body)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) > 500:
        body = body[:499].rstrip() + "…"
    return body


def _topic_tag(post: SocialPost) -> str | None:
    """1~50자, 마침표·& 불가 (Threads API 제약)."""
    tags = post.hashtags or []
    if not tags:
        return None
    tag = tags[0].lstrip("#").replace(".", "").replace("&", "and").strip()
    return tag[:50] or None


def _create_carousel_items(client, urls: list[str]) -> tuple[list[str], str | None]:
    """카드뉴스 장마다 is_carousel_item 컨테이너를 만든다 (Threads API: 2~20장)."""
    ids = []
    for u in urls:
        r = client.post(
            f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
            params={"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true",
                    "access_token": THREADS_ACCESS_TOKEN},
        )
        cid = r.json().get("id") if r.status_code == 200 else None
        if not cid:
            return [], f"Carousel item 생성 실패: {r.text[:200]}"
        ids.append(cid)
    # 장별 이미지 처리 대기 — 바로 묶으면 "media not ready" 로 실패한다
    time.sleep(3 + len(ids))
    return ids, None


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

        # 이미지 URL 확인 — public URL이면 IMAGE 모드, 2장 이상이면 카드뉴스(CAROUSEL)
        slides = [u for u in (getattr(post, "image_urls", None) or [])
                  if u and u.startswith(("http://", "https://"))][:20]
        has_image = bool(slides) or bool(
            post.image_url
            and post.image_url.startswith(("http://", "https://"))
        )

        # Step 1: 미디어 컨테이너 생성
        with httpx.Client(timeout=30.0) as client:
            params = {
                "text": full_text,
                "access_token": THREADS_ACCESS_TOKEN,
            }

            if len(slides) >= 2:
                children, err = _create_carousel_items(client, slides)
                if err:
                    return None, err
                params["media_type"] = "CAROUSEL"
                params["children"] = ",".join(children)
            elif has_image:
                params["media_type"] = "IMAGE"
                params["image_url"] = slides[0] if slides else post.image_url
            else:
                params["media_type"] = "TEXT"

            tag = _topic_tag(post)
            if tag:
                params["topic_tag"] = tag

            create_resp = client.post(
                f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
                params=params,
            )
            if create_resp.status_code != 200 and tag:
                # 이미지 게시물의 topic_tag 지원 여부가 문서에 명시돼 있지 않다 → 태그 빼고 한 번 더
                logger.warning("Threads topic_tag 포함 생성 실패, 태그 없이 재시도: %s", create_resp.text[:200])
                params.pop("topic_tag", None)
                create_resp = client.post(
                    f"{_GRAPH_API_BASE}/{THREADS_USER_ID}/threads",
                    params=params,
                )
            if create_resp.status_code != 200:
                return None, f"Container 생성 실패: {create_resp.text[:200]}"

            container_id = create_resp.json().get("id")
            if not container_id:
                return None, "Container ID 누락"

            # 컨테이너 처리 대기 (이미지·카드뉴스일 때 더 오래 대기)
            time.sleep(8 if len(slides) >= 2 else 5 if has_image else 2)

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

            # 출처 목록 댓글 (있을 때만)
            reply_text = getattr(post, "reply_text", None)
            if thread_id and reply_text:
                try:
                    _post_reply(client, thread_id, reply_text)
                except Exception as reply_err:
                    logger.warning("Threads 댓글 실패 (무시): %s", reply_err)

            return str(thread_id), None

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("Threads 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg


def _post_reply(client, parent_thread_id: str, reply_text: str) -> None:
    """메인 게시물에 출처 목록 댓글 달기."""
    from worker.social.brief import strip_emoji
    reply_text = strip_emoji(reply_text)[:500]

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
