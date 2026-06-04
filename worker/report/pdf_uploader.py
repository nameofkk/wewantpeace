"""PDF를 Supabase Storage에 업로드."""
import logging
import os

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
_BUCKET = "weekly-reports"


def upload_pdf(pdf_bytes: bytes, filename: str) -> str | None:
    """PDF 바이트를 Supabase Storage에 업로드하고 public URL 반환."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase Storage 미설정 — PDF 업로드 스킵")
        return None

    try:
        import httpx

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{filename}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/pdf",
                    "x-upsert": "true",
                },
                content=pdf_bytes,
            )
            if resp.status_code not in (200, 201):
                logger.error("PDF 업로드 실패: %s %s", resp.status_code, resp.text[:200])
                return None

        url = f"{SUPABASE_URL}/storage/v1/object/public/{_BUCKET}/{filename}"
        logger.info("PDF 업로드 완료: %s", url)
        return url
    except Exception:
        logger.exception("PDF 업로드 오류")
        return None
