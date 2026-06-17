"""프로모 구독(platform 'promo:%' + amount=0)을 유료 구독자 지표에서 분리하는지 검증.

프로모는 돈을 한 푼도 안 낸 무료 체험이라 'subscribers'(유료 구독자) 카운트에 섞이면
지표명이 거짓이 된다. bot-stats/admin stats가 쓰는 필터(_IS_PROMO_SUB, _active_not_expired)가
프로모는 promo_subscribers로 빼고 유료만 subscribers로 세는지 확인한다.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func

from backend.app.models.user import User
from backend.app.models.subscription import Subscription
from backend.app.routers.admin import _IS_PROMO_SUB, _active_not_expired


async def _make_user(db) -> User:
    u = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(u)
    await db.flush()
    return u


async def _add_sub(db, user, *, platform, amount, status="active", expires_at="future"):
    now = datetime.now(timezone.utc)
    if expires_at == "future":
        exp = now + timedelta(days=30)
    elif expires_at == "past":
        exp = now - timedelta(days=1)
    else:
        exp = expires_at  # None 등
    sub = Subscription(
        user_id=user.id, plan="pro", status=status, platform=platform,
        amount=amount, currency="USD", expires_at=exp,
    )
    db.add(sub)
    await db.flush()
    return sub


async def _counts(db):
    now = datetime.now(timezone.utc)
    paid = (await db.execute(
        select(func.count()).select_from(Subscription).where(_active_not_expired(now), ~_IS_PROMO_SUB)
    )).scalar() or 0
    promo = (await db.execute(
        select(func.count()).select_from(Subscription).where(_active_not_expired(now), _IS_PROMO_SUB)
    )).scalar() or 0
    return paid, promo


@pytest.mark.asyncio
async def test_promo_excluded_from_paid_counts(db):
    u = await _make_user(db)
    # 진짜 유료 구독 (web 결제, amount>0)
    await _add_sub(db, u, platform="web", amount=699)
    # dodopayments 유료 구독
    await _add_sub(db, await _make_user(db), platform="dodopayments", amount=699)
    # 프로모 무료 구독 (promo:CODE, amount=0)
    await _add_sub(db, await _make_user(db), platform="promo:THREADS", amount=0)
    await _add_sub(db, await _make_user(db), platform="promo:PRODUCTHUNT", amount=0)

    paid, promo = await _counts(db)
    assert paid == 2, "유료(web/dodo)만 subscribers에 잡혀야 함"
    assert promo == 2, "프로모 2건은 promo_subscribers로 분리돼야 함"


@pytest.mark.asyncio
async def test_expired_zombie_excluded_from_both(db):
    """status='active'여도 expires_at 지난 좀비는 유료/프로모 어느 쪽도 안 센다."""
    await _add_sub(db, await _make_user(db), platform="web", amount=699, expires_at="past")
    await _add_sub(db, await _make_user(db), platform="promo:THREADS", amount=0, expires_at="past")

    paid, promo = await _counts(db)
    assert paid == 0
    assert promo == 0


@pytest.mark.asyncio
async def test_promo_with_nonzero_amount_counts_as_paid(db):
    """platform이 promo:여도 amount>0이면(실수로 과금된 케이스) 유료로 본다 — 기준은 amount=0."""
    await _add_sub(db, await _make_user(db), platform="promo:WEIRD", amount=699)
    paid, promo = await _counts(db)
    assert paid == 1
    assert promo == 0


@pytest.mark.asyncio
async def test_null_expiry_active_paid_counts(db):
    """expires_at NULL(만료 시각 미설정)인 active 유료는 유효한 걸로 센다."""
    await _add_sub(db, await _make_user(db), platform="web", amount=699, expires_at=None)
    paid, promo = await _counts(db)
    assert paid == 1
    assert promo == 0
