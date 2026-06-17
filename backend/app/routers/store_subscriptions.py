"""
/subscriptions/store/* 스토어 IAP 구독 라우터 (Google Play / Apple App Store)
"""
from __future__ import annotations
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.subscription import Subscription
from backend.app.services.subscription_service import activate_store_subscription, handle_store_event
from backend.app.core.store_products import google_product_to_plan, apple_product_to_plan
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)
slog = structlog.get_logger()

router = APIRouter(prefix="/subscriptions/store", tags=["store-subscriptions"])

PACKAGE_NAME = "com.wewantpeace.app"


# ── 스키마 ────────────────────────────────────────────────────────────────────

class GoogleVerifyBody(BaseModel):
    purchase_token: str
    product_id: str
    source: Optional[str] = None


class AppleVerifyBody(BaseModel):
    transaction_id: str
    product_id: str = ""
    source: Optional[str] = None


class RestoreBody(BaseModel):
    platform: str  # "android" | "ios"
    purchase_token: str = ""  # Google
    transaction_id: str = ""  # Apple


# ── Google Play 영수증 검증 ──────────────────────────────────────────────────

@router.post("/google/verify")
async def google_verify(
    body: GoogleVerifyBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Android 앱에서 구매 후 호출: purchase_token + product_id 검증."""
    from backend.app.services.google_play_billing import verify_subscription, acknowledge_subscription

    plan = google_product_to_plan(body.product_id)
    if not plan:
        raise HTTPException(422, detail="알 수 없는 상품 ID입니다.")

    result = await verify_subscription(PACKAGE_NAME, body.purchase_token)
    if not result.get("valid"):
        raise HTTPException(400, detail=f"구독 검증 실패: {result.get('error', 'invalid')}")

    # acknowledge 처리
    if result.get("acknowledgement_state", 0) == 0:
        await acknowledge_subscription(PACKAGE_NAME, body.product_id, body.purchase_token)

    # 만료 시간 파싱
    expiry_time = result.get("expiry_time", "")
    expires_at = None
    if expiry_time:
        try:
            expires_at = datetime.fromisoformat(expiry_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    sub = await activate_store_subscription(
        user_id=current_user.id,
        platform="android",
        product_id=body.product_id,
        # 거래번호(transaction_id)는 구글 orderId를 쓴다.
        # purchase_token은 구독 내내 고정이라 갱신 검증마다 같은 값이 들어가서
        # payment_history (platform, pg_transaction_id, status) 유니크 인덱스에 충돌했음.
        # orderId는 갱신마다 새로 발급돼서 충돌이 안 난다. 없으면 토큰으로 폴백.
        # 단, 구독 조회 키인 original_transaction_id는 토큰 그대로 둬야 매칭이 된다.
        transaction_id=(result.get("order_id") or body.purchase_token)[:200],
        original_transaction_id=body.purchase_token[:256],
        expires_at=expires_at,
        auto_renewing=result.get("auto_renewing", True),
        raw_response=result.get("raw", {}),
        db=db,
    )

    slog.info(
        "store_subscription_verified",
        platform="android",
        user_id=str(current_user.id),
        plan=sub.plan,
        product_id=body.product_id,
        source=body.source,
    )

    return {
        "status": "ok",
        "plan": sub.plan,
        "subscription_id": str(sub.id),
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
    }


# ── Apple 영수증 검증 ────────────────────────────────────────────────────────

@router.post("/apple/verify")
async def apple_verify(
    body: AppleVerifyBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """iOS 앱에서 구매 후 호출: transaction_id 검증."""
    from backend.app.services.apple_storekit import verify_transaction

    result = await verify_transaction(body.transaction_id)
    if not result.get("valid"):
        raise HTTPException(400, detail=f"거래 검증 실패: {result.get('error', 'invalid')}")

    product_id = result.get("product_id", body.product_id)
    plan = apple_product_to_plan(product_id)
    if not plan:
        raise HTTPException(422, detail="알 수 없는 상품 ID입니다.")

    # 만료 시간 파싱
    expires_date = result.get("expires_date")
    expires_at = None
    if expires_date:
        try:
            if isinstance(expires_date, (int, float)):
                expires_at = datetime.fromtimestamp(expires_date / 1000, tz=timezone.utc)
            else:
                expires_at = datetime.fromisoformat(str(expires_date).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    sub = await activate_store_subscription(
        user_id=current_user.id,
        platform="ios",
        product_id=product_id,
        transaction_id=result.get("transaction_id", body.transaction_id),
        original_transaction_id=result.get("original_transaction_id", body.transaction_id),
        expires_at=expires_at,
        auto_renewing=result.get("auto_renew_status", 0) == 1,
        raw_response=result.get("raw", {}),
        db=db,
    )

    slog.info(
        "store_subscription_verified",
        platform="ios",
        user_id=str(current_user.id),
        plan=sub.plan,
        product_id=product_id,
        source=body.source,
    )

    return {
        "status": "ok",
        "plan": sub.plan,
        "subscription_id": str(sub.id),
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
    }


# ── 구매 복원 ────────────────────────────────────────────────────────────────

@router.post("/restore")
async def restore_purchase(
    body: RestoreBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """기기 변경 시 구매 복원."""
    if body.platform == "android" and body.purchase_token:
        from backend.app.services.google_play_billing import verify_subscription
        result = await verify_subscription(PACKAGE_NAME, body.purchase_token)
        if not result.get("valid"):
            raise HTTPException(400, detail="유효하지 않은 구독입니다.")

        # original_transaction_id로 기존 구독 찾기
        existing = await db.execute(
            select(Subscription).where(
                Subscription.store_original_transaction_id == body.purchase_token[:256],
            ).limit(1)
        )
        sub = existing.scalar_one_or_none()
        if sub:
            # 보안: 타인의 구독은 복원 불가 (소유자만 복원 가능)
            if sub.user_id != current_user.id:
                raise HTTPException(403, detail="해당 구독의 소유자가 아닙니다. 고객지원에 문의해주세요.")
            sub.status = "active"
            await db.flush()

            user_result = await db.execute(select(User).where(User.id == current_user.id))
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = sub.plan
                user.admin_plan_override = False
                await sync_area_activation(current_user.id, sub.plan, db)
            await db.flush()
            return {"status": "ok", "plan": sub.plan}

        raise HTTPException(404, detail="복원할 구독을 찾을 수 없습니다.")

    elif body.platform == "ios" and body.transaction_id:
        from backend.app.services.apple_storekit import verify_transaction
        result = await verify_transaction(body.transaction_id)
        if not result.get("valid"):
            raise HTTPException(400, detail="유효하지 않은 거래입니다.")

        orig_tx_id = result.get("original_transaction_id", body.transaction_id)
        existing = await db.execute(
            select(Subscription).where(
                Subscription.store_original_transaction_id == orig_tx_id,
            ).limit(1)
        )
        sub = existing.scalar_one_or_none()
        if sub:
            # 보안: 타인의 구독은 복원 불가 (소유자만 복원 가능)
            if sub.user_id != current_user.id:
                raise HTTPException(403, detail="해당 구독의 소유자가 아닙니다. 고객지원에 문의해주세요.")
            sub.status = "active"
            await db.flush()

            user_result = await db.execute(select(User).where(User.id == current_user.id))
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = sub.plan
                user.admin_plan_override = False
                await sync_area_activation(current_user.id, sub.plan, db)
            await db.flush()
            return {"status": "ok", "plan": sub.plan}

        raise HTTPException(404, detail="복원할 구독을 찾을 수 없습니다.")

    raise HTTPException(422, detail="platform과 token/transaction_id가 필요합니다.")


# ── Google RTDN 웹훅 ─────────────────────────────────────────────────────────

@router.post("/google/rtdn")
async def google_rtdn_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Google Play Real-Time Developer Notifications (Pub/Sub push)."""
    # Pub/Sub push 인증: URL에 포함된 토큰 검증
    webhook_token = settings.google_rtdn_webhook_token
    if not webhook_token:
        logger.error("Google RTDN: GOOGLE_RTDN_WEBHOOK_TOKEN 미설정 — 웹훅 거부")
        raise HTTPException(403, detail="Webhook token not configured")
    request_token = request.query_params.get("token", "")
    if not request_token or request_token != webhook_token:
        logger.warning("Google RTDN: 인증 실패 (잘못된 토큰)")
        raise HTTPException(403, detail="Forbidden")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="잘못된 요청 형식입니다.")

    # Pub/Sub 메시지 디코딩
    message = payload.get("message", {})
    data_b64 = message.get("data", "")
    if not data_b64:
        return {"status": "no_data"}

    try:
        data = json.loads(base64.b64decode(data_b64))
    except Exception:
        raise HTTPException(400, detail="메시지 디코딩 실패")

    notification = data.get("subscriptionNotification", {})
    if not notification:
        return {"status": "not_subscription"}

    notification_type = notification.get("notificationType", 0)
    purchase_token = notification.get("purchaseToken", "")
    subscription_id = notification.get("subscriptionId", "")

    if not purchase_token:
        return {"status": "no_token"}

    # Google API로 최신 상태 조회
    from backend.app.services.google_play_billing import verify_subscription

    result = await verify_subscription(PACKAGE_NAME, purchase_token)

    # notificationType → 이벤트 타입 매핑
    GOOGLE_NOTIFICATION_MAP = {
        1: "RECOVERED",
        2: "RENEWED",
        3: "CANCELED",
        4: "PURCHASED",
        5: "ON_HOLD",
        6: "IN_GRACE_PERIOD",
        7: "RESTARTED",
        12: "REVOKED",
        13: "EXPIRED",
    }
    event_type = GOOGLE_NOTIFICATION_MAP.get(notification_type, f"UNKNOWN_{notification_type}")

    # 만료 시간
    expiry_time = result.get("expiry_time", "")
    expires_at = None
    if expiry_time:
        try:
            expires_at = datetime.fromisoformat(expiry_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    # 거래번호(transaction_id)는 구글 orderId를 쓴다.
    # purchase_token은 구독 내내 고정이라 갱신마다 같은 값이 들어가서
    # payment_history (platform, pg_transaction_id, status) 유니크 인덱스에 충돌했음.
    # orderId는 갱신마다 새로 발급돼서 충돌이 안 난다. 없으면 토큰으로 폴백.
    # 단, 구독 조회 키인 original_transaction_id는 토큰 그대로 둬야 매칭이 된다.
    order_id = result.get("order_id") or purchase_token

    await handle_store_event(
        platform="android",
        event_type=event_type,
        original_transaction_id=purchase_token[:256],
        transaction_id=order_id[:200],
        product_id=result.get("product_id"),
        expires_at=expires_at,
        auto_renewing=result.get("auto_renewing", False),
        raw_payload=data,
        db=db,
    )

    return {"status": "ok"}


# ── Apple Server Notifications V2 ────────────────────────────────────────────

@router.post("/apple/notifications")
async def apple_notifications_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Apple App Store Server Notifications V2."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="잘못된 요청 형식입니다.")

    signed_payload = payload.get("signedPayload", "")
    if not signed_payload:
        return {"status": "no_payload"}

    from backend.app.services.apple_storekit import decode_apple_notification

    decoded = decode_apple_notification(signed_payload)
    if not decoded:
        raise HTTPException(400, detail="Notification 디코딩 실패")

    notification_type = decoded.get("notificationType", "")
    subtype = decoded.get("subtype", "")
    data = decoded.get("data", {})
    tx_info = data.get("transactionInfo", {})

    if not tx_info:
        return {"status": "no_transaction_info"}

    original_transaction_id = tx_info.get("originalTransactionId", "")
    transaction_id = tx_info.get("transactionId", "")
    product_id = tx_info.get("productId", "")
    expires_date = tx_info.get("expiresDate")

    expires_at = None
    if expires_date:
        try:
            if isinstance(expires_date, (int, float)):
                expires_at = datetime.fromtimestamp(expires_date / 1000, tz=timezone.utc)
            else:
                expires_at = datetime.fromisoformat(str(expires_date).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    renewal_info = data.get("renewalInfo", {})
    auto_renewing = renewal_info.get("autoRenewStatus", 0) == 1

    await handle_store_event(
        platform="ios",
        event_type=notification_type,
        original_transaction_id=original_transaction_id,
        transaction_id=transaction_id,
        product_id=product_id,
        expires_at=expires_at,
        auto_renewing=auto_renewing,
        raw_payload=decoded,
        db=db,
    )

    return {"status": "ok"}
