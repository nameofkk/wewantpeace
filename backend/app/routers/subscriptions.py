"""
/subscriptions/* 구독 API (스토어 IAP 전용, Toss 제거됨)
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

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

PLANS = {
    "pro": {"name": "Pro", "amount": 4900, "features": [
        {"ko": "관심국가 5개", "en": "5 monitored countries"},
        {"ko": "실시간 이슈 지도", "en": "Real-time issue map"},
        {"ko": "속보 알림 (미확인 포함)", "en": "Fast alerts (breaking news)"},
        {"ko": "긴장도 히스토리 30일", "en": "30-day tension history"},
        {"ko": "KScore 필터 조정 (3.0~10.0)", "en": "KScore filter (3.0–10.0)"},
        {"ko": "토픽 필터", "en": "Topic filter"},
        {"ko": "방해금지 시간", "en": "Quiet hours"},
    ]},
    "pro_plus": {"name": "Pro+", "amount": 9900, "features": [
        {"ko": "Pro 기능 전체", "en": "All Pro features"},
        {"ko": "관심국가 무제한", "en": "Unlimited monitored countries"},
        {"ko": "긴장도 히스토리 90일", "en": "90-day tension history"},
        {"ko": "KScore 필터 조정 (1.5~10.0)", "en": "KScore filter (1.5–10.0)"},
    ]},
}


# ── 스키마 ────────────────────────────────────────────────────────────────────

class CancelBody(BaseModel):
    reason: str = "사용자 요청"


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
                Subscription.status.in_(["active", "grace_period"]),
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
        raise HTTPException(404, detail="활성 구독이 없습니다.")

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
            "message": f"구독은 {store_name}에서 직접 취소해주세요.",
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
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "message": f"구독이 취소되었습니다. {sub.expires_at.strftime('%Y년 %m월 %d일') if sub.expires_at else '기간 종료'} 까지 서비스를 이용할 수 있습니다.",
    }


@router.post("/start-trial")
async def start_trial(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pro 7일 무료 체험. Pro만 가능, Pro+ 제외. 1회만."""
    if current_user.plan != "free":
        raise HTTPException(409, detail="이미 유료 플랜을 사용 중입니다.")

    # 이전 trial 이력 확인 (trial_end IS NOT NULL)
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.trial_end.isnot(None),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail="무료 체험은 1회만 가능합니다.")

    from datetime import timedelta

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
    await sync_area_activation(current_user.id, "pro", db)
    await db.flush()

    return {
        "status": "ok",
        "plan": "pro",
        "trial_end": trial_end.isoformat(),
    }
