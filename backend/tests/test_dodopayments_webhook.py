"""
DodoPayments 웹훅 순서 역전(payment.succeeded ↔ subscription.active) 시
매출(PaymentHistory)이 유실되지 않고 백필되는지 검증.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func

from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.routers import dodopayments

PRO_PRODUCT = "prod_pro_monthly_test"


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    # product_id → plan 매핑이 동작하도록 테스트용 상품 ID 주입
    monkeypatch.setattr(settings, "dodo_product_pro", PRO_PRODUCT, raising=False)
    # area 활성화는 본 테스트 범위 밖 → no-op
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(dodopayments, "sync_area_activation", _noop)


async def _make_user(db, *, email="u@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        firebase_uid=f"fb_{uuid.uuid4().hex[:10]}",
        email=email,
        plan="free",
        display_name="테스터",
    )
    db.add(user)
    await db.flush()
    return user


def _sub_active_event(*, dodo_sub_id, user_id, product_id=PRO_PRODUCT):
    return SimpleNamespace(
        subscription_id=dodo_sub_id,
        product_id=product_id,
        customer=SimpleNamespace(customer_id="cus_123"),
        metadata={"user_id": str(user_id)},
        next_billing_date=datetime(2026, 7, 10, tzinfo=timezone.utc),
        expires_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        recurring_pre_tax_amount=699,
        currency="USD",
        cancel_at_next_billing_date=False,
    )


def _payment_event(*, dodo_sub_id, payment_id, amount=699, metadata=None):
    return SimpleNamespace(
        payment_id=payment_id,
        subscription_id=dodo_sub_id,
        total_amount=amount,
        currency="USD",
        metadata=metadata,
        customer=SimpleNamespace(customer_id="cus_123"),
    )


async def _count_payments(db) -> int:
    res = await db.execute(select(func.count()).select_from(PaymentHistory))
    return res.scalar_one()


@pytest.mark.asyncio
async def test_normal_order_active_then_payment(db):
    """정상 순서: subscription.active → payment.succeeded → 결제가 user/sub에 연결."""
    user = await _make_user(db)
    dodo_sub_id = "sub_normal"

    await dodopayments._handle_subscription_active(
        _sub_active_event(dodo_sub_id=dodo_sub_id, user_id=user.id), db
    )
    await dodopayments._handle_payment_succeeded(
        _payment_event(dodo_sub_id=dodo_sub_id, payment_id="pay_1"), db
    )

    res = await db.execute(select(PaymentHistory))
    payments = res.scalars().all()
    assert len(payments) == 1
    ph = payments[0]
    assert ph.user_id == user.id
    assert ph.subscription_id is not None
    assert ph.status == "success"


@pytest.mark.asyncio
async def test_reordered_payment_first_no_metadata(db):
    """역전 순서 + metadata 없음: 미연결 매출로 기록 → active 때 user/sub 백필."""
    user = await _make_user(db)
    dodo_sub_id = "sub_race"

    # payment가 먼저 도착 (metadata=None → user 즉시 연결 불가)
    await dodopayments._handle_payment_succeeded(
        _payment_event(dodo_sub_id=dodo_sub_id, payment_id="pay_race", metadata=None), db
    )

    res = await db.execute(select(PaymentHistory))
    ph = res.scalars().one()
    assert ph.user_id is None  # 아직 누구 건지 모름
    assert ph.subscription_id is None
    assert ph.amount == 699
    assert ph.pg_response["dodo_subscription_id"] == dodo_sub_id
    assert ph.pg_response["pending_link"] is True

    # 이제 subscription.active 도착 → 백필
    await dodopayments._handle_subscription_active(
        _sub_active_event(dodo_sub_id=dodo_sub_id, user_id=user.id), db
    )

    await db.refresh(ph)
    sub = await dodopayments._find_sub_by_dodo_id(dodo_sub_id, db)
    assert sub is not None
    assert ph.user_id == user.id
    assert ph.subscription_id == sub.id
    assert ph.pg_response["pending_link"] is False
    # 매출이 그대로 1건 보존
    assert await _count_payments(db) == 1


@pytest.mark.asyncio
async def test_reordered_payment_first_with_metadata(db):
    """역전 순서 + metadata.user_id 있음: user는 즉시 연결, sub만 백필."""
    user = await _make_user(db)
    dodo_sub_id = "sub_race_meta"

    await dodopayments._handle_payment_succeeded(
        _payment_event(
            dodo_sub_id=dodo_sub_id, payment_id="pay_meta",
            metadata={"user_id": str(user.id)},
        ),
        db,
    )

    res = await db.execute(select(PaymentHistory))
    ph = res.scalars().one()
    assert ph.user_id == user.id        # metadata로 즉시 연결
    assert ph.subscription_id is None   # 구독은 아직 없음

    await dodopayments._handle_subscription_active(
        _sub_active_event(dodo_sub_id=dodo_sub_id, user_id=user.id), db
    )
    await db.refresh(ph)
    sub = await dodopayments._find_sub_by_dodo_id(dodo_sub_id, db)
    assert ph.subscription_id == sub.id
    assert await _count_payments(db) == 1


@pytest.mark.asyncio
async def test_duplicate_payment_idempotent(db):
    """같은 payment_id 웹훅 재전송 → 매출 중복 기록 안 됨."""
    user = await _make_user(db)
    dodo_sub_id = "sub_dup"
    await dodopayments._handle_subscription_active(
        _sub_active_event(dodo_sub_id=dodo_sub_id, user_id=user.id), db
    )
    await dodopayments._handle_payment_succeeded(
        _payment_event(dodo_sub_id=dodo_sub_id, payment_id="pay_dup"), db
    )
    # 재전송
    await dodopayments._handle_payment_succeeded(
        _payment_event(dodo_sub_id=dodo_sub_id, payment_id="pay_dup"), db
    )
    assert await _count_payments(db) == 1
