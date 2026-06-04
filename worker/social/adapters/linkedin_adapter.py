"""LinkedIn 어댑터 — OAuth2 + Company Page UGC Post (API v2).

LinkedIn 2026 알고리즘 최적화:
- 네이티브 텍스트 포스트 최우선 (외부 링크 페널티 있음)
- 첫 줄 hook + 줄바꿈 → "더 보기" 유도
- 해시태그 3~5개 (너무 많으면 페널티)
- 이미지 첨부 시 engagement 2~3x 상승
- 1300자 이하 최적 (긴 글 노출 감소)
- bilingual 포맷: EN + KO + CTA
"""
import logging
import os
import re

from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ORG_ID = os.getenv("LINKEDIN_ORG_ID", "")

_API_BASE = "https://api.linkedin.com/v2"
_MAX_TEXT_LEN = 1300


def is_configured() -> bool:
    return bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_ORG_ID)


def _build_text(post: SocialPost) -> str:
    """LinkedIn 최적화 본문 (1300자 한도).

    LinkedIn 전용 톤:
    - 전문적이면서 접근 가능한 톤
    - 원문 전체 유지 (bilingual)
    - hook 첫 줄 → "더 보기" 유도
    - 해시태그 3~5개 (본문 하단)
    - URL 포함 (프로필 유입)
    """
    body = post.body_text

    # 마크다운 제거
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', body)
    body = re.sub(r'__(.+?)__', r'\1', body)
    body = re.sub(r'_(.+?)_', r'\1', body)

    # 기존 CTA/URL 라인 정리 (LinkedIn 전용으로 교체)
    body = re.sub(r'^[→🔗📈].*$', '', body, flags=re.MULTILINE).strip()
    body = re.sub(r'https?://\S+', '', body).strip()
    body = re.sub(r'www\.\S+', '', body).strip()
    body = re.sub(r'#\w+', '', body).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    # LinkedIn CTA: 전문적 톤 + URL
    cta = "\n\n---\n🌍 Track conflicts in real-time · 실시간 분쟁 추적\nwww.wewantpeace.live"

    # 해시태그 (3~5개)
    hashtag_str = " ".join(post.hashtags[:5]) if post.hashtags else ""
    if hashtag_str:
        cta = f"{cta}\n\n{hashtag_str}"

    full_text = body + cta

    # 1300자 초과 시 잘라내기
    if len(full_text) > _MAX_TEXT_LEN:
        max_body = _MAX_TEXT_LEN - len(cta) - 3
        full_text = f"{body[:max_body]}...{cta}"

    return full_text


def _register_image(image_url: str, headers: dict) -> str | None:
    """LinkedIn에 이미지를 등록(registerUpload) → 업로드 → asset URN 반환.

    LinkedIn 이미지 첨부 3-step:
    1. registerUpload → uploadUrl + asset
    2. PUT 이미지 바이너리 to uploadUrl
    3. asset URN을 ugcPost에 포함
    """
    try:
        import httpx

        author = f"urn:li:organization:{LINKEDIN_ORG_ID}"

        # Step 1: Register upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        with httpx.Client(timeout=30.0) as client:
            reg_resp = client.post(
                f"{_API_BASE}/assets?action=registerUpload",
                headers=headers,
                json=register_payload,
            )
            if reg_resp.status_code not in (200, 201):
                logger.warning("LinkedIn 이미지 등록 실패: %s", reg_resp.text[:200])
                return None

            reg_data = reg_resp.json()
            upload_url = (
                reg_data.get("value", {})
                .get("uploadMechanism", {})
                .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
                .get("uploadUrl")
            )
            asset = reg_data.get("value", {}).get("asset")

            if not upload_url or not asset:
                logger.warning("LinkedIn 이미지 등록 응답 불완전: %s", reg_data)
                return None

            # Step 2: 이미지 다운로드 + 업로드
            img_resp = client.get(image_url, timeout=15.0)
            if img_resp.status_code != 200:
                logger.warning("이미지 다운로드 실패 [%s]: %s", img_resp.status_code, image_url[:80])
                return None

            upload_resp = client.put(
                upload_url,
                content=img_resp.content,
                headers={
                    "Authorization": headers["Authorization"],
                    "Content-Type": "image/png",
                },
            )
            if upload_resp.status_code not in (200, 201):
                logger.warning("LinkedIn 이미지 업로드 실패: %s", upload_resp.status_code)
                return None

            logger.info("LinkedIn 이미지 업로드 완료: asset=%s", asset)
            return asset

    except Exception:
        logger.warning("LinkedIn 이미지 등록/업로드 오류: %s", image_url[:80])
        return None


def publish(post: SocialPost) -> tuple[str | None, str | None]:
    """LinkedIn Company Page에 UGC 포스트 발행.

    Returns:
        (platform_post_id, error_message)
    """
    if not is_configured():
        return None, "LinkedIn API 키 미설정"

    try:
        import httpx

        full_text = _build_text(post)
        author = f"urn:li:organization:{LINKEDIN_ORG_ID}"

        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # 이미지 첨부 처리
        media_content = None
        if post.image_url and post.image_url.startswith(("http://", "https://")):
            asset_urn = _register_image(post.image_url, headers)
            if asset_urn:
                media_content = {
                    "status": "READY",
                    "description": {"text": "WeWantPeace Conflict Report"},
                    "media": asset_urn,
                    "title": {"text": "WeWantPeace"},
                }

        # UGC Post payload 구성
        specific_content: dict = {}
        if media_content:
            specific_content = {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "IMAGE",
                    "media": [media_content],
                }
            }
        else:
            specific_content = {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "NONE",
                }
            }

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": specific_content,
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{_API_BASE}/ugcPosts",
                headers=headers,
                json=payload,
            )

            if resp.status_code in (200, 201):
                post_urn = resp.json().get("id", "")
                logger.info(
                    "LinkedIn 발행 완료: urn=%s, post_id=%s", post_urn, post.id
                )
                return post_urn, None
            else:
                error_detail = resp.text[:500]
                logger.error(
                    "LinkedIn 발행 실패 [post=%s]: %s %s",
                    post.id, resp.status_code, error_detail,
                )
                return None, f"LinkedIn API {resp.status_code}: {error_detail}"

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error("LinkedIn 발행 실패 [post=%s]: %s", post.id, error_msg)
        return None, error_msg
