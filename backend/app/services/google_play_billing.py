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

    # CANCELED 는 "자동 갱신을 끔"이지 만료가 아니다 — 이미 낸 기간(expiryTime)까지는 써야 한다.
    # 예전엔 valid=False 로 봐서 2026-10-10 Pro+ 결제(EUR 10.99)를 결제 2시간 뒤 만료 처리했다.
    canceled_but_paid = False
    if subscription_state == "SUBSCRIPTION_STATE_CANCELED" and expiry_time:
        try:
            from datetime import datetime, timezone
            canceled_but_paid = datetime.fromisoformat(expiry_time.replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except (ValueError, AttributeError):
            canceled_but_paid = False
    item = line_items[0] if line_items else {}
    offer_id = ((item.get("offerDetails") or {}).get("offerId") or "").lower()
    # 지금 체험 기간인가: offerPhase 가 있으면 그걸 따르고, 없으면 "체험 혜택으로 산 첫 주기"(갱신 주문 번호 ..N 이 아직 없음)로 본다.
    # offerId 는 체험이 끝나 유료로 넘어간 뒤에도 그대로 남아서 그것만 보면 유료 손님을 체험으로 잘못 센다.
    if item.get("offerPhase"):
        in_free_trial = "freeTrial" in item["offerPhase"]
    else:
        in_free_trial = "trial" in offer_id and ".." not in order_id
    cancel_time = ((result.get("canceledStateContext") or {}).get("userInitiatedCancellation") or {}).get("cancelTime", "")

    return {
        "valid": subscription_state in (
            "SUBSCRIPTION_STATE_ACTIVE",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
        ) or canceled_but_paid,
        "canceled": subscription_state == "SUBSCRIPTION_STATE_CANCELED",
        "cancel_time": cancel_time,
        "in_free_trial": in_free_trial,
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
