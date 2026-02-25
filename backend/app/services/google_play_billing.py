"""Google Play Developer API v3 영수증 검증 서비스."""
from __future__ import annotations
import json
import logging
from typing import Any

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def _get_android_publisher_service():
    """Google API 클라이언트 생성 (서비스 계정 인증)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_path = settings.google_play_service_account_key_path
    if not key_path:
        raise RuntimeError("GOOGLE_PLAY_SERVICE_ACCOUNT_KEY_PATH not configured")

    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    return build("androidpublisher", "v3", credentials=credentials, cache_discovery=False)


async def verify_subscription(
    package_name: str,
    purchase_token: str,
) -> dict[str, Any]:
    """
    Google Play subscriptionsv2.get으로 구독 상태 검증.
    반환: {
        "valid": bool,
        "product_id": str,
        "expiry_time_millis": int,
        "auto_renewing": bool,
        "state": str,
        "acknowledgement_state": int,
        "raw": dict,
    }
    """
    import asyncio

    def _verify():
        service = _get_android_publisher_service()
        result = service.purchases().subscriptionsv2().get(
            packageName=package_name,
            token=purchase_token,
        ).execute()
        return result

    try:
        result = await asyncio.to_thread(_verify)
    except Exception as e:
        logger.error("Google Play 구독 검증 실패: %s", e)
        return {"valid": False, "error": str(e)}

    # subscriptionsv2 응답 파싱
    subscription_state = result.get("subscriptionState", "")
    line_items = result.get("lineItems", [])
    product_id = line_items[0].get("productId", "") if line_items else ""
    expiry_time = line_items[0].get("expiryTime", "") if line_items else ""
    auto_renewing = result.get("autoResumeTimeMillis") is None and subscription_state in (
        "SUBSCRIPTION_STATE_ACTIVE",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    )

    return {
        "valid": subscription_state in (
            "SUBSCRIPTION_STATE_ACTIVE",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
        ),
        "product_id": product_id,
        "expiry_time": expiry_time,
        "auto_renewing": auto_renewing,
        "state": subscription_state,
        "acknowledgement_state": result.get("acknowledgementState", 0),
        "raw": result,
    }


async def acknowledge_subscription(
    package_name: str,
    subscription_id: str,
    purchase_token: str,
) -> bool:
    """구독 인정(acknowledge). 구매 후 3일 내 필수."""
    import asyncio

    def _ack():
        service = _get_android_publisher_service()
        service.purchases().subscriptions().acknowledge(
            packageName=package_name,
            subscriptionId=subscription_id,
            token=purchase_token,
        ).execute()

    try:
        await asyncio.to_thread(_ack)
        return True
    except Exception as e:
        logger.error("Google Play acknowledge 실패: %s", e)
        return False
