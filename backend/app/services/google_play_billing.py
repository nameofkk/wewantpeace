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

    sa_json = settings.google_play_service_account_json
    if not sa_json:
        raise RuntimeError("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON not configured")

    service_account_info = json.loads(sa_json)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
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
        "order_id": str,   # 최신 주문 ID(latestOrderId). 갱신마다 바뀌므로 결제 거래번호로 사용.
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
    # latestOrderId: 구독 가입 주문 → 갱신될 때마다 ..0, ..1 식으로 새 주문 ID가 붙는다.
    # purchase_token은 구독 내내 그대로라 갱신 결제 거래번호로 쓰면 중복되므로, 이 값을 쓴다.
    order_id = result.get("latestOrderId", "")
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
        "order_id": order_id,
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
