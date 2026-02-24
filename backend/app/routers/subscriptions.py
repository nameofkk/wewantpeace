"""
/subscriptions/* 구독 및 결제 API (토스페이먼츠)
"""
from __future__ import annotations
import hashlib
import logging
import os
import uuid

logger = logging.getLogger(__name__)
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "test_sk_placeholder")
TOSS_BILLING_URL = "https://api.tosspayments.com/v1/billing"
TOSS_BILLING_AUTH_URL = "https://api.tosspayments.com/v1/billing/authorizations"

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


def _toss_auth_header():
    import base64
    key_bytes = f"{TOSS_SECRET_KEY}:".encode()
    return "Basic " + base64.b64encode(key_bytes).decode()


# ── 스키마 ────────────────────────────────────────────────────────────────────

class TossReadyOut(BaseModel):
    customer_key: str
    amount: int
    order_name: str
    plan: str


class TossConfirmBody(BaseModel):
    auth_key: str
    customer_key: str
    plan: str = "pro"


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
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"plan": "free", "status": "free"}

    return {
        "plan": sub.plan,
        "status": sub.status,
        "amount": sub.amount,
        "started_at": sub.started_at.isoformat(),
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "next_billing_at": sub.next_billing_at.isoformat() if sub.next_billing_at else None,
    }


@router.post("/toss/ready", response_model=TossReadyOut)
async def toss_ready(
    plan: str = "pro",
    current_user: User = Depends(get_current_user),
):
    if plan not in PLANS:
        raise HTTPException(422, detail="유효하지 않은 플랜입니다.")

    # 사용자별 고정 customer_key (user_id 해시)
    customer_key = hashlib.sha256(str(current_user.id).encode()).hexdigest()[:64]
    plan_info = PLANS[plan]

    return TossReadyOut(
        customer_key=customer_key,
        amount=plan_info["amount"],
        order_name=f"WeWantPeace {plan_info['name']} 정기구독",
        plan=plan,
    )


@router.post("/toss/confirm")
async def toss_confirm(
    body: TossConfirmBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.plan not in PLANS:
        raise HTTPException(422, detail="유효하지 않은 플랜입니다.")

    # 토스페이먼츠 billingKey 발급
    billing_key = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TOSS_BILLING_AUTH_URL}/issue",
                headers={"Authorization": _toss_auth_header()},
                json={"authKey": body.auth_key, "customerKey": body.customer_key},
            )
            if resp.status_code == 200:
                billing_key = resp.json().get("billingKey")
    except Exception as e:
        # 테스트 환경에서는 더미 billingKey 사용
        if TOSS_SECRET_KEY.startswith("test_"):
            billing_key = f"test_billing_{body.customer_key[:16]}"
        else:
            logger.error("토스페이먼츠 billingKey 발급 오류: %s", e)
            raise HTTPException(502, detail="결제 서비스 연결에 실패했습니다. 잠시 후 다시 시도해주세요.")

    if not billing_key:
        raise HTTPException(400, detail="billingKey 발급에 실패했습니다.")

    # 기존 활성 구독 취소
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        )
    )
    for old_sub in existing.scalars().all():
        old_sub.status = "cancelled"
        old_sub.cancelled_at = datetime.now(timezone.utc)

    # 새 구독 생성
    now = datetime.now(timezone.utc)
    plan_info = PLANS[body.plan]
    sub = Subscription(
        user_id=current_user.id,
        plan=body.plan,
        status="active",
        billing_key=billing_key,
        customer_key=body.customer_key,
        amount=plan_info["amount"],
        started_at=now,
        expires_at=now + timedelta(days=30),
        next_billing_at=now + timedelta(days=30),
    )
    db.add(sub)

    # 첫 결제 기록 (billingKey 발급 시 첫 결제 발생)
    db.add(PaymentHistory(
        user_id=current_user.id,
        subscription_id=sub.id,
        amount=plan_info["amount"],
        status="success",
        pg_transaction_id=billing_key,
        pg_response={"plan": body.plan, "billing_key": billing_key},
    ))

    # 사용자 플랜 업데이트
    current_user.plan = body.plan
    await db.flush()

    return {"status": "ok", "plan": body.plan, "subscription_id": str(sub.id)}


@router.post("/cancel")
async def cancel_subscription(
    body: CancelBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, detail="활성 구독이 없습니다.")

    now = datetime.now(timezone.utc)
    sub.status = "cancelled"
    sub.cancelled_at = now
    # expires_at은 그대로 유지 — 만료일까지 서비스 사용 가능
    await db.flush()

    return {
        "status": "cancelled",
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "message": f"구독이 취소되었습니다. {sub.expires_at.strftime('%Y년 %m월 %d일') if sub.expires_at else '기간 종료'} 까지 서비스를 이용할 수 있습니다.",
    }


@router.post("/toss/webhook")
async def toss_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """토스페이먼츠 정기결제 웹훅 처리."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail="잘못된 요청 형식입니다.")

    event_type = payload.get("eventType", "")
    billing_key = payload.get("billingKey")

    if not billing_key:
        return {"status": "ignored"}

    # billing_key로 구독 조회
    result = await db.execute(
        select(Subscription).where(Subscription.billing_key == billing_key)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"status": "subscription_not_found"}

    now = datetime.now(timezone.utc)

    if event_type == "PAYMENT_STATUS_CHANGED":
        payment_status = payload.get("status", "")
        amount = payload.get("totalAmount", sub.amount)
        order_id = payload.get("orderId", "")

        if payment_status == "DONE":
            # 결제 성공
            db.add(PaymentHistory(
                user_id=sub.user_id,
                subscription_id=sub.id,
                amount=amount,
                status="success",
                pg_transaction_id=order_id,
                pg_response=payload,
            ))
            sub.expires_at = (sub.expires_at or now) + timedelta(days=30)
            sub.next_billing_at = sub.expires_at

            # 사용자 플랜 갱신
            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = sub.plan

        elif payment_status in ("ABORTED", "EXPIRED"):
            # 결제 실패
            db.add(PaymentHistory(
                user_id=sub.user_id,
                subscription_id=sub.id,
                amount=amount,
                status="failed",
                pg_transaction_id=order_id,
                pg_response=payload,
            ))
            # 3회 연속 실패 시 구독 만료 처리는 별도 배치로

    await db.flush()
    return {"status": "ok"}
