"""오브젝트 저장소 — 파일을 어디에 두고 어떤 주소로 내보내는가.

## 왜 생겼나

원래 파일은 Supabase Storage에 올렸다. 2026-08-21에 DB를 Railway로 옮기면서 파일도 같이
옮겼는데(5,137개·2.5GB), **Railway 버킷은 공개 URL을 못 준다**(presigned 최대 90일 또는 프록시).
`social-cards`는 SNS 카드 이미지라 영구 공개 주소가 필수라서 **Cloudflare R2**로 갔다.
R2는 커스텀 도메인(`cdn.wewantpeace.live`)으로 영구 공개 주소를 주고 이그레스가 무료다.

## 지금 어디에 쓰나

- 커뮤니티 이미지 업로드(`routers/community.py`)
- 앞으로 늘어날 업로드도 여기를 지난다. 각 라우터가 저마다 S3 서명을 짜면 한쪽만 고쳐지는 날이 온다.

## 설정이 없으면

`R2_*`가 비어 있으면 `None`을 돌려준다. 부르는 쪽이 로컬 저장으로 물러선다(개발 환경).
**조용히 성공한 척하지 않는다** — 올리기에 실패하면 예외를 던진다.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

_UNSIGNED = "UNSIGNED-PAYLOAD"


def _cfg() -> dict[str, str] | None:
    """R2 설정 한 벌. 하나라도 비면 쓰지 않는다(반쯤 설정된 상태로 도는 게 제일 나쁘다)."""
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
    """AWS SigV4 서명.

    boto3를 새로 들이는 대신 서명을 직접 만든다 — 우리가 쓰는 건 PUT 하나뿐이고,
    의존성 하나를 아끼는 편이 배포 이미지에도 낫다. 규격은 AWS 문서 그대로다.
    """
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


async def put_object(key: str, data: bytes, content_type: str) -> str | None:
    """파일 하나를 올리고 **공개 주소**를 돌려준다. 설정이 없으면 `None`.

    `key`는 `버킷폴더/파일명` 꼴로 준다(예: `community-uploads/abc.png`). 옛 Supabase 경로와
    같은 모양을 유지해야 이미 DB에 저장된 주소를 도메인만 바꿔 치환할 수 있다.
    """
    cfg = _cfg()
    if cfg is None:
        return None

    path = f"/{cfg['bucket']}/{quote(key)}"
    headers = _auth_headers(cfg, "PUT", path, data, content_type)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(f"{cfg['endpoint']}{path}", headers=headers, content=data)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"R2 업로드 실패: {resp.status_code} {resp.text[:200]}")

    return f"{cfg['public_base']}/{key}"
