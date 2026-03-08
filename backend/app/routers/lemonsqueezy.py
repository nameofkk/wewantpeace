"""
/payments/ls/* LemonSqueezy 웹 결제 라우터
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments/ls", tags=["lemonsqueezy"])

LEMONSQUEEZY_API_BASE = "https://api.lemonsqueezy.com/v1"

# variant_id -> plan 매핑 (설정 기반)
def _variant_to_plan(variant_id: str) -> str | None:
    if variant_id == settings.lemonsqueezy_variant_pro:
        return "pro"
    if variant_id == settings.lemonsqueezy_variant_proplus:
        return "pro_plus"
    return None


def _plan_to_variant(plan: str) -> str | None:
    if plan == "pro":
        return settings.lemonsqueezy_variant_pro
    if plan == "pro_plus":
        return settings.lemonsqueezy_variant_proplus
    return None


# ── 스키마 ────────────────────────────────────────────────────────────────────

class CheckoutBody(BaseModel):
    plan: str  # "pro" | "pro_plus"


# ── Checkout 생성 ─────────────────────────────────────────────────────────────

@router.post("/create-checkout")
async def create_checkout(
    body: CheckoutBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LemonSqueezy Checkout URL 생성."""
    if body.plan not in ("pro", "pro_plus"):
        raise HTTPException(422, detail="유효하지 않은 플랜입니다. pro 또는 pro_plus만 가능합니다.")

    variant_id = _plan_to_variant(body.plan)
    if not variant_id:
        raise HTTPException(500, detail="LemonSqueezy variant가 설정되지 않았습니다.")

    if not settings.lemonsqueezy_api_key:
        raise HTTPException(500, detail="LemonSqueezy API 키가 설정되지 않았습니다.")

    if not settings.lemonsqueezy_store_id:
        raise HTTPException(500, detail="LemonSqueezy Store ID가 설정되지 않았습니다.")

    # 기존 활성 구독 처리 (업그레이드/중복 방지)
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "trial", "grace_period"]),
        )
    )
    now = datetime.now(timezone.utc)
    for existing_sub in existing_result.scalars().all():
        if existing_sub.status == "trial":
            # trial → 만료 처리
            existing_sub.status = "expired"
            existing_sub.updated_at = now
            logger.info("Trial 구독 만료 처리: user=%s → 유료 전환 진행", current_user.id)
        elif existing_sub.plan == body.plan:
            # 같은 플랜 중복 구독 차단
            raise HTTPException(409, detail={"code": "ALREADY_SUBSCRIBED", "message": "이미 같은 플랜의 활성 구독이 있습니다."})
        else:
            # 다른 플랜 업그레이드/다운그레이드 → 기존 구독 취소 처리
            existing_sub.status = "cancelled"
            existing_sub.cancelled_at = now
            existing_sub.updated_at = now
            logger.info(
                "기존 구독 취소: user=%s plan=%s → 새 플랜 %s 전환",
                current_user.id, existing_sub.plan, body.plan,
            )

    # 최근 만료된 trial/promo 확인 → 할인 코드 자동 적용
    discount_code = None
    if settings.lemonsqueezy_welcome_discount:
        recent_expired = await db.execute(
            select(Subscription).where(
                Subscription.user_id == current_user.id,
                Subscription.status == "expired",
                Subscription.platform.in_(["trial", "promo:PRODUCTHUNT"]),
                Subscription.expires_at >= now - timedelta(days=7),
            ).limit(1)
        )
        if recent_expired.scalar_one_or_none():
            discount_code = settings.lemonsqueezy_welcome_discount

    # LemonSqueezy Checkout API 호출
    checkout_data = {
        "email": current_user.email or "",
        "custom": {
            "user_id": str(current_user.id),
        },
    }
    if discount_code:
        checkout_data["discount_code"] = discount_code

    checkout_payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": checkout_data,
                "product_options": {
                    "redirect_url": "https://www.wewantpeace.live/upgrade/success",
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": settings.lemonsqueezy_store_id,
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": variant_id,
                    }
                },
            },
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{LEMONSQUEEZY_API_BASE}/checkouts",
            json=checkout_payload,
            headers={
                "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json",
            },
        )

    if resp.status_code not in (200, 201):
        logger.error("LemonSqueezy checkout 생성 실패: %s %s", resp.status_code, resp.text)
        raise HTTPException(502, detail="결제 페이지 생성에 실패했습니다.")

    data = resp.json()
    checkout_url = data["data"]["attributes"]["url"]

    logger.info(
        "LemonSqueezy checkout 생성: user=%s plan=%s variant=%s discount=%s",
        current_user.id, body.plan, variant_id, discount_code,
    )

    return {
        "checkout_url": checkout_url,
        "plan": body.plan,
        **({"discount_applied": True, "discount_code": discount_code} if discount_code else {}),
    }


# ── 웹훅 ─────────────────────────────────────────────────────────────────────

def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """HMAC-SHA256 서명 검증."""
    if not settings.lemonsqueezy_webhook_secret:
        logger.warning("LemonSqueezy webhook secret 미설정 - 서명 검증 불가")
        return False
    expected = hmac.new(
        settings.lemonsqueezy_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def lemonsqueezy_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """LemonSqueezy 웹훅 수신 (서명 검증, 인증 불필요)."""
    raw_body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not _verify_webhook_signature(raw_body, signature):
        logger.warning("LemonSqueezy 웹훅 서명 검증 실패")
        raise HTTPException(403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="잘못된 요청 형식입니다.")

    event_name = payload.get("meta", {}).get("event_name", "")
    custom_data = payload.get("meta", {}).get("custom_data", {})
    user_id_str = custom_data.get("user_id", "")
    data_attrs = payload.get("data", {}).get("attributes", {})

    ls_subscription_id = str(payload.get("data", {}).get("id", ""))
    ls_customer_id = str(data_attrs.get("customer_id", ""))
    ls_variant_id = str(data_attrs.get("variant_id", data_attrs.get("first_subscription_item", {}).get("variant_id", "")))

    logger.info(
        "LemonSqueezy 웹훅 수신: event=%s user_id=%s ls_sub=%s",
        event_name, user_id_str, ls_subscription_id,
    )

    if event_name == "subscription_created":
        await _handle_subscription_created(
            user_id_str=user_id_str,
            ls_subscription_id=ls_subscription_id,
            ls_customer_id=ls_customer_id,
            ls_variant_id=ls_variant_id,
            attrs=data_attrs,
            db=db,
        )
    elif event_name == "subscription_payment_success":
        await _handle_payment_success(
            ls_subscription_id=ls_subscription_id,
            attrs=data_attrs,
            db=db,
        )
    elif event_name == "subscription_cancelled":
        await _handle_subscription_cancelled(
            ls_subscription_id=ls_subscription_id,
            attrs=data_attrs,
            db=db,
        )
    elif event_name == "subscription_expired":
        await _handle_subscription_expired(
            ls_subscription_id=ls_subscription_id,
            db=db,
        )
    elif event_name == "subscription_payment_failed":
        await _handle_payment_failed(
            ls_subscription_id=ls_subscription_id,
            db=db,
        )
    else:
        logger.info("LemonSqueezy 처리하지 않는 이벤트: %s", event_name)

    return {"status": "ok"}


# ── 이벤트 핸들러 ─────────────────────────────────────────────────────────────

def _parse_ls_datetime(dt_str: str | None) -> datetime | None:
    """LemonSqueezy ISO 8601 날짜 문자열 파싱."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def _find_sub_by_ls_id(ls_subscription_id: str, db: AsyncSession) -> Subscription | None:
    """ls_subscription_id로 구독 조회."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.ls_subscription_id == ls_subscription_id,
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _handle_subscription_created(
    user_id_str: str,
    ls_subscription_id: str,
    ls_customer_id: str,
    ls_variant_id: str,
    attrs: dict,
    db: AsyncSession,
) -> None:
    """subscription_created: 새 구독 생성, user.plan 변경."""
    import uuid as _uuid

    if not user_id_str:
        logger.error("LemonSqueezy subscription_created: user_id 누락")
        return

    try:
        user_id = _uuid.UUID(user_id_str)
    except ValueError:
        logger.error("LemonSqueezy subscription_created: 유효하지 않은 user_id=%s", user_id_str)
        return

    # 사용자 조회
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error("LemonSqueezy subscription_created: 사용자를 찾을 수 없음 user_id=%s", user_id_str)
        return

    # variant -> plan 매핑
    plan = _variant_to_plan(ls_variant_id)
    if not plan:
        logger.error("LemonSqueezy subscription_created: 알 수 없는 variant_id=%s", ls_variant_id)
        return

    # 만료 시간
    renews_at = _parse_ls_datetime(attrs.get("renews_at"))
    ends_at = _parse_ls_datetime(attrs.get("ends_at"))
    expires_at = renews_at or ends_at

    now = datetime.now(timezone.utc)

    # 기존 LemonSqueezy 구독이 있으면 업데이트
    existing = await _find_sub_by_ls_id(ls_subscription_id, db)
    if existing:
        existing.status = "active"
        existing.plan = plan
        existing.ls_variant_id = ls_variant_id
        existing.expires_at = expires_at
        existing.next_billing_at = expires_at  # renews_at가 다음 결제일
        existing.updated_at = now
    else:
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            platform="lemonsqueezy",
            amount=int(attrs.get("first_subscription_item", {}).get("price", 0)) // 100,
            currency=attrs.get("currency", "USD").upper(),
            ls_subscription_id=ls_subscription_id,
            ls_customer_id=ls_customer_id,
            ls_variant_id=ls_variant_id,
            auto_renewing=attrs.get("cancelled", False) is False,
            started_at=now,
            expires_at=expires_at,
            next_billing_at=expires_at,  # renews_at가 다음 결제일
        )
        db.add(sub)

    # user.plan 변경
    user.plan = plan
    await sync_area_activation(user_id, plan, db)
    await db.flush()

    logger.info(
        "LemonSqueezy 구독 생성 완료: user=%s plan=%s ls_sub=%s",
        user_id, plan, ls_subscription_id,
    )


async def _handle_payment_success(
    ls_subscription_id: str,
    attrs: dict,
    db: AsyncSession,
) -> None:
    """subscription_payment_success: expires_at 갱신."""
    sub = await _find_sub_by_ls_id(ls_subscription_id, db)
    if not sub:
        logger.warning("LemonSqueezy payment_success: 구독을 찾을 수 없음 ls_sub=%s", ls_subscription_id)
        return

    renews_at = _parse_ls_datetime(attrs.get("renews_at"))
    ends_at = _parse_ls_datetime(attrs.get("ends_at"))
    new_expires = renews_at or ends_at

    if new_expires:
        sub.expires_at = new_expires
        sub.next_billing_at = new_expires  # renews_at가 다음 결제일

    now = datetime.now(timezone.utc)
    sub.status = "active"
    sub.updated_at = now

    # PaymentHistory 기록
    amount = int(attrs.get("first_subscription_item", {}).get("price", 0)) // 100
    history = PaymentHistory(
        user_id=sub.user_id,
        subscription_id=sub.id,
        amount=amount,
        currency=attrs.get("currency", "USD").upper(),
        status="success",
        platform="lemonsqueezy",
        pg_transaction_id=ls_subscription_id,
        pg_response=attrs,
    )
    db.add(history)
    await db.flush()

    logger.info(
        "LemonSqueezy 결제 성공: ls_sub=%s expires_at=%s",
        ls_subscription_id, new_expires,
    )


async def _handle_subscription_cancelled(
    ls_subscription_id: str,
    attrs: dict,
    db: AsyncSession,
) -> None:
    """subscription_cancelled: status=cancelled, 만료일까지는 사용 가능."""
    sub = await _find_sub_by_ls_id(ls_subscription_id, db)
    if not sub:
        logger.warning("LemonSqueezy cancelled: 구독을 찾을 수 없음 ls_sub=%s", ls_subscription_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "cancelled"
    sub.cancelled_at = now
    sub.auto_renewing = False

    # ends_at가 있으면 갱신
    ends_at = _parse_ls_datetime(attrs.get("ends_at"))
    if ends_at:
        sub.expires_at = ends_at

    sub.updated_at = now
    await db.flush()

    logger.info("LemonSqueezy 구독 취소: ls_sub=%s expires_at=%s", ls_subscription_id, sub.expires_at)


async def _handle_subscription_expired(
    ls_subscription_id: str,
    db: AsyncSession,
) -> None:
    """subscription_expired: user.plan=free, 구독 만료 처리."""
    sub = await _find_sub_by_ls_id(ls_subscription_id, db)
    if not sub:
        logger.warning("LemonSqueezy expired: 구독을 찾을 수 없음 ls_sub=%s", ls_subscription_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "expired"
    sub.updated_at = now

    # 사용자 free 전환
    user_result = await db.execute(select(User).where(User.id == sub.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.plan = "free"
        await sync_area_activation(user.id, "free", db)

    await db.flush()

    logger.info("LemonSqueezy 구독 만료: ls_sub=%s user=%s", ls_subscription_id, sub.user_id)


async def _handle_payment_failed(
    ls_subscription_id: str,
    db: AsyncSession,
) -> None:
    """subscription_payment_failed: status=billing_retry."""
    sub = await _find_sub_by_ls_id(ls_subscription_id, db)
    if not sub:
        logger.warning("LemonSqueezy payment_failed: 구독을 찾을 수 없음 ls_sub=%s", ls_subscription_id)
        return

    now = datetime.now(timezone.utc)
    sub.status = "billing_retry"
    sub.updated_at = now
    await db.flush()

    logger.info("LemonSqueezy 결제 실패: ls_sub=%s user=%s", ls_subscription_id, sub.user_id)
