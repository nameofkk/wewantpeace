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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

PLANS = {
    "pro": {"name": "Pro", "amount": 4900, "features": [
        "관심국가 무제한",
        "Fast 알림",
        "긴장도 히스토리 30일",
        "커뮤니티 우선 노출",
    ]},
    "pro_plus": {"name": "Pro+", "amount": 9900, "features": [
        "Pro 기능 전체",
        "긴장도 히스토리 90일",
        "개인 API 접근",
        "알림 룰 설정",
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
    await db.flush()

    return {
        "status": "cancelled",
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "message": f"구독이 취소되었습니다. {sub.expires_at.strftime('%Y년 %m월 %d일') if sub.expires_at else '기간 종료'} 까지 서비스를 이용할 수 있습니다.",
    }
