"""Supabase Storage 이미지 업로더 — 카드 이미지를 public URL로 변환."""
import logging
import os

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_BUCKET = "social-cards"


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def upload_image(local_path: str, post_id: str) -> str | None:
    """로컬 이미지 파일을 Supabase Storage에 업로드하고 public URL 반환.

    Args:
        local_path: 로컬 PNG 파일 경로
        post_id: 포스트 ID (파일명에 사용)

    Returns:
        public URL 또는 None (실패 시)
    """
    if not is_configured():
        logger.warning("Supabase Storage 미설정 — 이미지 업로드 스킵")
        return None

    if not os.path.exists(local_path):
        logger.warning("이미지 파일 없음: %s", local_path)
        return None

    try:
        import httpx

        object_path = f"cards/{post_id}.png"

        with open(local_path, "rb") as f:
            image_data = f.read()

        with httpx.Client(timeout=30.0) as client:
            # upsert=true로 덮어쓰기 허용
            resp = client.post(
                f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{object_path}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "image/png",
                    "x-upsert": "true",
                },
                content=image_data,
            )

            if resp.status_code not in (200, 201):
                logger.error(
                    "Supabase Storage 업로드 실패 [%s]: %s",
                    resp.status_code, resp.text[:200],
                )
                return None

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{_BUCKET}/{object_path}"
        logger.info("이미지 업로드 완료: %s", public_url)

        # 업로드 성공 후 로컬 임시 파일 정리
        try:
            os.unlink(local_path)
        except Exception:
            pass

        return public_url

    except Exception:
        logger.exception("Supabase Storage 업로드 오류 [post=%s]", post_id)
        return None
