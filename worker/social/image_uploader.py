"""SNS 카드 이미지 업로더 — Cloudflare R2에 올리고 public URL로 변환.

2026-08-21에 파일 저장소를 Supabase Storage에서 R2로 옮겼다(backend/app/core/
object_store.py, 커밋 ba6cd26). 그런데 이 워커 모듈은 그때 같이 안 바뀌고
Supabase 엔드포인트를 그대로 호출하고 있었다. SUPABASE_URL/SUPABASE_SERVICE_KEY가
더 이상 설정돼 있지 않아 is_configured()가 항상 False → upload_image()가 항상
None → card_generator.py가 로컬 임시 경로(/tmp/social-card-...)를 그대로
post.image_url에 저장 → Threads 어댑터는 image_url이 http(s)로 시작할 때만
IMAGE 모드를 쓰므로(threads_adapter.py) 조용히 TEXT 모드로 떨어졌다.
실측(2026-09-15): 최근 7일 social_posts 226건 전부 image_url이 로컬 경로.

object_store.py는 async(httpx.AsyncClient)인데 이 모듈은 sync 컨텍스트(카드 생성이
동기 PIL/Playwright 작업이라 실행기 스레드에서 돎)에서 불려 그대로 재사용할 수
없다 — 같은 SigV4 서명 로직을 sync httpx.Client로 다시 구현한다.
"""
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _cfg() -> dict[str, str] | None:
    cfg = {
        "endpoint": os.getenv("R2_ENDPOINT", "").rstrip("/"),
        "key": os.getenv("R2_ACCESS_KEY_ID", ""),
        "secret": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "bucket": os.getenv("R2_BUCKET", ""),
        "public_base": os.getenv("R2_PUBLIC_BASE", "").rstrip("/"),
    }
    return cfg if all(cfg.values()) else None


def is_configured() -> bool:
    return _cfg() is not None


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _auth_headers(cfg: dict[str, str], method: str, path: str, payload: bytes, content_type: str) -> dict[str, str]:
    """AWS SigV4 서명 (object_store.py와 동일 규격, R2는 S3 호환 API)."""
    host = cfg["endpoint"].split("://", 1)[1]
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    region = "auto"
    service = "s3"

    payload_hash = hashlib.sha256(payload).hexdigest()
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    k_date = _sign(f"AWS4{cfg['secret']}".encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    return {
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={cfg['key']}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Content-Type": content_type,
    }


def upload_image(local_path: str, post_id: str) -> str | None:
    """로컬 이미지 파일을 R2에 업로드하고 public URL 반환.

    Args:
        local_path: 로컬 PNG 파일 경로
        post_id: 포스트 ID (파일명에 사용)

    Returns:
        public URL 또는 None (실패 시)
    """
    cfg = _cfg()
    if cfg is None:
        logger.warning("R2 미설정 — 이미지 업로드 스킵")
        return None

    if not os.path.exists(local_path):
        logger.warning("이미지 파일 없음: %s", local_path)
        return None

    try:
        import httpx

        key = f"cards/{post_id}.png"
        path = f"/{cfg['bucket']}/{quote(key)}"

        with open(local_path, "rb") as f:
            image_data = f.read()

        headers = _auth_headers(cfg, "PUT", path, image_data, "image/png")

        with httpx.Client(timeout=30.0) as client:
            resp = client.put(f"{cfg['endpoint']}{path}", headers=headers, content=image_data)

            if resp.status_code not in (200, 201):
                logger.error(
                    "R2 업로드 실패 [%s]: %s",
                    resp.status_code, resp.text[:200],
                )
                return None

        public_url = f"{cfg['public_base']}/{key}"
        logger.info("이미지 업로드 완료: %s", public_url)

        # 업로드 성공 후 로컬 임시 파일 정리
        try:
            os.unlink(local_path)
        except Exception:
            pass

        return public_url

    except Exception:
        logger.exception("R2 업로드 오류 [post=%s]", post_id)
        return None
