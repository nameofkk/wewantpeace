"""Apple App Store Server API v2 영수증 검증 서비스."""
from __future__ import annotations
import base64
import json
import logging
import time
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.x509 import load_der_x509_certificate
from cryptography.x509.oid import NameOID

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Apple 환경 URL
APPLE_PRODUCTION_URL = "https://api.storekit.itunes.apple.com"
APPLE_SANDBOX_URL = "https://api.storekit-sandbox.itunes.apple.com"


def _get_base_url() -> str:
    if settings.apple_environment.lower() == "production":
        return APPLE_PRODUCTION_URL
    return APPLE_SANDBOX_URL


def _generate_apple_jwt() -> str:
    """App Store Server API 인증용 JWT 생성 (ES256)."""
    import jwt  # PyJWT

    key_path = settings.apple_private_key_path
    if not key_path:
        raise RuntimeError("APPLE_PRIVATE_KEY_PATH not configured")

    with open(key_path, "r") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iss": settings.apple_issuer_id,
        "iat": now,
        "exp": now + 3600,  # 1시간
        "aud": "appstoreconnect-v1",
        "bid": settings.apple_bundle_id,
    }
    headers = {
        "alg": "ES256",
        "kid": settings.apple_key_id,
        "typ": "JWT",
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


async def verify_transaction(transaction_id: str) -> dict[str, Any]:
    """
    App Store Server API v2로 거래 검증.
    GET /inApps/v1/transactions/{transactionId}
    """
    import httpx

    base_url = _get_base_url()
    token = _generate_apple_jwt()

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{base_url}/inApps/v1/transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code != 200:
        logger.error("Apple 거래 검증 실패: status=%d body=%s", resp.status_code, resp.text[:500])
        return {"valid": False, "error": f"HTTP {resp.status_code}"}

    data = resp.json()
    # signedTransactionInfo JWS 디코딩
    signed_info = data.get("signedTransactionInfo", "")
    tx_info = _decode_jws_payload(signed_info)

    if not tx_info:
        return {"valid": False, "error": "JWS decode failed"}

    return {
        "valid": True,
        "product_id": tx_info.get("productId", ""),
        "original_transaction_id": tx_info.get("originalTransactionId", ""),
        "transaction_id": tx_info.get("transactionId", ""),
        "expires_date": tx_info.get("expiresDate"),
        "auto_renew_status": tx_info.get("autoRenewStatus", 0),
        "raw": tx_info,
    }


async def get_subscription_statuses(original_transaction_id: str) -> dict[str, Any]:
    """
    구독 상태 조회.
    GET /inApps/v1/subscriptions/{originalTransactionId}
    """
    import httpx

    base_url = _get_base_url()
    token = _generate_apple_jwt()

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{base_url}/inApps/v1/subscriptions/{original_transaction_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code != 200:
        logger.error("Apple 구독 상태 조회 실패: status=%d", resp.status_code)
        return {"valid": False, "error": f"HTTP {resp.status_code}"}

    data = resp.json()
    return {"valid": True, "raw": data}


def _b64url_decode(s: str) -> bytes:
    """Base64url decode with proper padding."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _decode_jws_payload(jws_string: str) -> dict | None:
    """JWS payload 디코딩 (서명 검증 없이, Apple API 응답 등 TLS로 보호되는 경우용)."""
    if not jws_string:
        return None
    try:
        parts = jws_string.split(".")
        if len(parts) != 3:
            return None
        return json.loads(_b64url_decode(parts[1]))
    except Exception as e:
        logger.error("JWS payload 디코딩 실패: %s", e)
        return None


def _verify_apple_jws(jws_string: str) -> dict | None:
    """
    Apple JWS 서명 검증 + payload 디코딩.
    x5c 인증서 체인 검증 → ES256 서명 검증 → payload 반환.
    Webhook 등 외부에서 수신한 JWS에 반드시 사용.
    """
    if not jws_string:
        return None
    try:
        parts = jws_string.split(".")
        if len(parts) != 3:
            logger.error("Apple JWS: 유효하지 않은 형식 (파트 %d개)", len(parts))
            return None

        # 1) 헤더에서 x5c 인증서 체인 추출
        header = json.loads(_b64url_decode(parts[0]))
        x5c = header.get("x5c", [])
        if len(x5c) < 2:
            logger.error("Apple JWS: x5c 체인 너무 짧음 (%d)", len(x5c))
            return None

        # 2) DER 인증서 로드
        certs = [load_der_x509_certificate(base64.b64decode(c)) for c in x5c]

        # 3) 인증서 체인 검증: 각 인증서가 다음 인증서에 의해 발급됨
        for i in range(len(certs) - 1):
            certs[i].verify_directly_issued_by(certs[i + 1])

        # 4) 루트 인증서 검증: 자기서명 + Apple 발급
        root = certs[-1]
        root.verify_directly_issued_by(root)  # 자기서명 확인
        root_cn_attrs = root.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not root_cn_attrs or "Apple Root CA" not in root_cn_attrs[0].value:
            logger.error("Apple JWS: 루트 인증서가 Apple이 아님: %s", root.subject)
            return None

        root_org_attrs = root.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        if not root_org_attrs or "Apple" not in root_org_attrs[0].value:
            logger.error("Apple JWS: 루트 인증서 조직이 Apple이 아님: %s", root.subject)
            return None

        # 5) JWS 서명 검증 (leaf 인증서의 공개키 사용)
        alg = header.get("alg", "")
        if alg != "ES256":
            logger.error("Apple JWS: 지원하지 않는 알고리즘: %s", alg)
            return None

        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        signature_bytes = _b64url_decode(parts[2])
        leaf_public_key = certs[0].public_key()
        leaf_public_key.verify(signature_bytes, signing_input, ec.ECDSA(hashes.SHA256()))

        # 6) Payload 디코딩
        return json.loads(_b64url_decode(parts[1]))

    except Exception as e:
        logger.error("Apple JWS 검증 실패: %s", e)
        return None


def decode_apple_notification(signed_payload: str) -> dict | None:
    """Apple Server Notification V2 signedPayload 검증 + 디코딩 (서명 검증 포함)."""
    payload = _verify_apple_jws(signed_payload)
    if not payload:
        return None
    # 중첩 JWS (signedTransactionInfo, signedRenewalInfo) 도 서명 검증
    if "data" in payload:
        data = payload["data"]
        if "signedTransactionInfo" in data:
            data["transactionInfo"] = _verify_apple_jws(data["signedTransactionInfo"])
        if "signedRenewalInfo" in data:
            data["renewalInfo"] = _verify_apple_jws(data["signedRenewalInfo"])
    return payload
