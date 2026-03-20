"""
/subscriptions/* 구독 API (스토어 IAP 전용, Toss 제거됨)
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.subscription import Subscription
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

PROMO_CODES = {
    "PRODUCTHUNT": {"plan": "pro", "days": 7, "description": "Product Hunt launch offer"},
    "THREADS": {"plan": "pro_plus", "days": 14, "description": "Threads 친구들 전용 Pro+ 2주 체험"},
    "testerforyou": {"plan": "pro_plus", "days": 30, "description": "테스터 전용 Pro+ 1개월"},
}

PLANS = {
    "pro": {"name": "Pro", "amount": 4900, "features": [
        {"ko": "관심 국가 5개", "en": "5 monitored countries"},
        {"ko": "내 국가 변경", "en": "Change home country"},
        {"ko": "실시간 이슈 지도", "en": "Real-time issue map"},
        {"ko": "속보 알림 (미확인 포함)", "en": "Fast alerts (breaking news)"},
        {"ko": "일일 알림 10건", "en": "10 daily alerts"},
        {"ko": "KScore 필터 조정 (3.0~10.0)", "en": "KScore filter (3.0–10.0)"},
        {"ko": "토픽 필터", "en": "Topic filter"},
        {"ko": "방해금지 시간", "en": "Quiet hours"},
        {"ko": "30일 히스토리", "en": "30-day history"},
    ]},
    "pro_plus": {"name": "Pro+", "amount": 9900, "features": [
        {"ko": "Pro 기능 전체", "en": "All Pro features"},
        {"ko": "관심 국가 무제한", "en": "Unlimited monitored countries"},
        {"ko": "일일 알림 50건", "en": "50 daily alerts"},
        {"ko": "KScore 필터 조정 (1.5~10.0)", "en": "KScore filter (1.5–10.0)"},
        {"ko": "90일 히스토리", "en": "90-day history"},
    ]},
}


# ── 스키마 ────────────────────────────────────────────────────────────────────

class CancelBody(BaseModel):
    reason: str = "사용자 요청"


class RedeemPromoBody(BaseModel):
    code: str


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("/plans")
async def get_plans():
    return [
        {
            "id": plan_id,
            "name": info["name"],
            "amount": info["amount"],
            "currency": "KRW",
            "features": info["features"],
        }
        for plan_id, info in PLANS.items()
    ]


@router.get("/my")
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            or_(
                Subscription.status.in_(["active", "trial", "grace_period"]),
                and_(
                    Subscription.status == "cancelled",
                    Subscription.expires_at > now,
                ),
            ),
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"plan": "free", "status": "free"}

    return {
        "plan": sub.plan,
        "status": sub.status,
        "amount": sub.amount,
        "platform": sub.platform,
        "auto_renewing": sub.auto_renewing,
        "started_at": sub.started_at.isoformat(),
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "next_billing_at": sub.next_billing_at.isoformat() if sub.next_billing_at else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
    }


@router.post("/cancel")
async def cancel_subscription(
    body: CancelBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "grace_period"]),
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, detail={"code": "NO_ACTIVE_SUBSCRIPTION"})

    # 스토어 구독은 스토어에서 직접 취소해야 함
    if sub.platform in ("android", "ios"):
        store_name = "Google Play" if sub.platform == "android" else "App Store"
        manage_url = (
            "https://play.google.com/store/account/subscriptions"
            if sub.platform == "android"
            else "https://apps.apple.com/account/subscriptions"
        )
        return {
            "status": "store_cancel_required",
            "code": "STORE_CANCEL_REQUIRED",
            "store": store_name,
            "manage_url": manage_url,
            "platform": sub.platform,
        }

    # 웹 구독 취소 (기존 로직)
    now = datetime.now(timezone.utc)
    sub.status = "cancelled"
    sub.cancelled_at = now
    # 만료일이 이미 지났으면 즉시 free 전환 + 관심국가 동기화
    if not sub.expires_at or sub.expires_at <= now:
        current_user.plan = "free"
        await sync_area_activation(current_user.id, "free", db)
    await db.flush()

    return {
        "status": "cancelled",
        "code": "SUBSCRIPTION_CANCELLED",
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
    }


@router.post("/start-trial")
async def start_trial(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pro 7일 무료 체험. Pro만 가능, Pro+ 제외. 무료 혜택 계정당 1회."""
    if current_user.plan != "free":
        raise HTTPException(409, detail={"code": "ALREADY_PAID_PLAN"})

    # 이전 trial 이력 확인 (trial_end IS NOT NULL)
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.trial_end.isnot(None),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "TRIAL_ALREADY_USED"})

    # 프로모 이력 확인 — 무료 혜택은 계정당 총 1회
    promo_existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.platform.like("promo:%"),
        ).limit(1)
    )
    if promo_existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "FREE_BENEFIT_ALREADY_USED"})

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=7)

    sub = Subscription(
        user_id=current_user.id,
        plan="pro",
        status="trial",
        amount=0,
        platform="trial",
        started_at=now,
        trial_start=now,
        trial_end=trial_end,
        expires_at=trial_end,
    )
    db.add(sub)

    current_user.plan = "pro"
    current_user.admin_plan_override = False
    await sync_area_activation(current_user.id, "pro", db)
    await db.flush()

    return {
        "status": "ok",
        "plan": "pro",
        "trial_end": trial_end.isoformat(),
    }


@router.post("/redeem-promo")
async def redeem_promo(
    body: RedeemPromoBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로모 코드로 Pro 활성화. 무료 혜택 계정당 1회."""
    code = body.code.strip().upper()
    promo = PROMO_CODES.get(code)
    if not promo:
        raise HTTPException(400, detail={"code": "INVALID_PROMO_CODE"})

    # 이미 유료 플랜이면 거부
    if current_user.plan != "free":
        raise HTTPException(409, detail={"code": "ALREADY_PAID_PLAN"})

    # 이미 같은 프로모 코드를 사용했으면 거부
    platform_tag = f"promo:{code}"
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.platform == platform_tag,
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "PROMO_ALREADY_USED"})

    # trial 이력 확인 — 무료 혜택은 계정당 총 1회
    trial_existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.trial_end.isnot(None),
        ).limit(1)
    )
    if trial_existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "FREE_BENEFIT_ALREADY_USED"})

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=promo["days"])

    sub = Subscription(
        user_id=current_user.id,
        plan=promo["plan"],
        status="active",
        amount=0,
        platform=platform_tag,
        started_at=now,
        expires_at=expires_at,
        auto_renewing=False,
    )
    db.add(sub)

    current_user.plan = promo["plan"]
    current_user.admin_plan_override = False
    await sync_area_activation(current_user.id, promo["plan"], db)
    await db.flush()

    logger.info("promo redeemed: user=%s code=%s plan=%s expires=%s",
                current_user.id, code, promo["plan"], expires_at.isoformat())

    return {
        "status": "ok",
        "plan": promo["plan"],
        "expires_at": expires_at.isoformat(),
        "promo_code": code,
    }
