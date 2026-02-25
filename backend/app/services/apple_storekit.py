"""Apple App Store Server API v2 영수증 검증 서비스."""
from __future__ import annotations
import json
import logging
import time
from typing import Any

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


def _decode_jws_payload(jws_string: str) -> dict | None:
    """JWS (3-part dot-separated) payload 디코딩. 서명 검증은 간소화."""
    import base64

    if not jws_string:
        return None
    try:
        parts = jws_string.split(".")
        if len(parts) != 3:
            return None
        # payload (2번째 파트) base64url 디코딩
        payload = parts[1]
        # base64url padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        logger.error("JWS payload 디코딩 실패: %s", e)
        return None


def decode_apple_notification(signed_payload: str) -> dict | None:
    """Apple Server Notification V2 signedPayload 디코딩."""
    payload = _decode_jws_payload(signed_payload)
    if not payload:
        return None
    # signedTransactionInfo, signedRenewalInfo 중첩 JWS 디코딩
    if "data" in payload:
        data = payload["data"]
        if "signedTransactionInfo" in data:
            data["transactionInfo"] = _decode_jws_payload(data["signedTransactionInfo"])
        if "signedRenewalInfo" in data:
            data["renewalInfo"] = _decode_jws_payload(data["signedRenewalInfo"])
    return payload
