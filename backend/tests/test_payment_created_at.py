"""payment_history.created_at 이 '처리 시각'(DB now)이 아니라 '실제 결제시각'으로 들어가는지 검증.

웹훅이 며칠 늦게 도착하거나 재전송돼도 매출 집계 날짜가 안 밀리게 하려고,
Dodo/스토어 웹훅 경로에서 결제 데이터에 담긴 실제 결제시각을 created_at에 박는다.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.routers import dodopayments
from backend.app.services import subscription_service


# 명백히 과거인 고정 결제시각 (현재는 2026년) — now()와 확실히 구분된다.
PAID_AT = datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _assert_same_instant(stored: datetime, expected: datetime):
    """SQLite가 tz를 떼고 저장할 수 있어 naive 구성요소로 비교한다."""
    s = stored.replace(tzinfo=None) if stored.tzinfo else stored
    e = expected.replace(tzinfo=None)
    assert s == e, f"{s} != {e}"


async def _make_user(db) -> User:
    u = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(u)
    await db.flush()
    return u


# ─── dodopayments: 결제시각 헬퍼 ───────────────────────────────────────────────

def test_payment_created_at_uses_data_created_at():
    data = SimpleNamespace(created_at=PAID_AT)
    assert dodopayments._payment_created_at(data) == PAID_AT


def test_payment_created_at_naive_assumed_utc():
    naive = datetime(2025, 3, 10, 12, 0, 0)
    got = dodopayments._payment_created_at(SimpleNamespace(created_at=naive))
    assert got.tzinfo is timezone.utc
    assert got.replace(tzinfo=None) == naive


def test_payment_created_at_missing_falls_back_to_now():
    got = dodopayments._payment_created_at(SimpleNamespace())
    # 폴백은 현재 시각 — 과거 고정값과 다르고 tz-aware
    assert got.tzinfo is not None
    assert got.year >= 2026


# ─── dodopayments: 구독 결제 / 고아 보존 / lifetime 경로 ───────────────────────

@pytest.mark.asyncio
async def test_subscription_payment_records_real_paid_at(db):
    user = await _make_user(db)
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="dodopayments",
        amount=699, currency="USD", billing_interval="monthly",
        dodo_subscription_id="dsub_paidat",
    )
    db.add(sub)
    await db.flush()

    data = SimpleNamespace(
        payment_id="pay_paidat_1", subscription_id="dsub_paidat",
        total_amount=699, currency="USD", created_at=PAID_AT,
    )
    await dodopayments._handle_payment_succeeded(data, db)

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "pay_paidat_1")
    )).scalar_one()
    _assert_same_instant(row.created_at, PAID_AT)


@pytest.mark.asyncio
async def test_orphan_payment_keeps_real_paid_at(db):
    """구독 못 찾아 보존하는 경로도 실제 결제시각을 유지한다."""
    user = await _make_user(db)
    data = SimpleNamespace(
        payment_id="pay_paidat_orphan", subscription_id="dsub_missing",
        total_amount=699, currency="USD", created_at=PAID_AT,
        metadata={"user_id": str(user.id), "plan": "pro"},
    )
    await dodopayments._handle_payment_succeeded(data, db)

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "pay_paidat_orphan")
    )).scalar_one()
    assert row.subscription_id is None
    _assert_same_instant(row.created_at, PAID_AT)


@pytest.mark.asyncio
async def test_lifetime_payment_records_real_paid_at(db, monkeypatch):
    """lifetime 일회성 결제도 실제 결제시각으로 기록."""
    from backend.app.core.config import settings
    # product_id → lifetime plan 매핑이 되도록 설정값을 픽스처에 맞춘다
    monkeypatch.setattr(settings, "dodo_product_pro_lifetime", "prod_life_pro", raising=False)

    user = await _make_user(db)
    data = SimpleNamespace(
        payment_id="pay_paidat_life", subscription_id=None,
        product_id="prod_life_pro", total_amount=29900, currency="USD",
        created_at=PAID_AT, metadata={"user_id": str(user.id)},
    )
    await dodopayments._handle_payment_succeeded(data, db)

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "pay_paidat_life")
    )).scalar_one()
    _assert_same_instant(row.created_at, PAID_AT)


# ─── subscription_service: 타임스탬프 파싱 헬퍼 ────────────────────────────────

def test_parse_store_timestamp_variants():
    f = subscription_service._parse_store_timestamp
    ms = 1741608000000  # 2025-03-10 12:00:00 UTC
    assert f(ms) == PAID_AT
    assert f(str(ms)) == PAID_AT
    assert f("2025-03-10T12:00:00Z") == PAID_AT
    assert f("2025-03-10T12:00:00+00:00") == PAID_AT
    # 폴백: 못 읽으면 None
    assert f(None) is None
    assert f("") is None
    assert f("not-a-date") is None


def test_store_event_paid_at_ios_and_android():
    f = subscription_service._store_event_paid_at
    ms = 1741608000000
    ios_payload = {"data": {"transactionInfo": {"purchaseDate": ms}}}
    assert f("ios", ios_payload, "RENEWED") == PAID_AT
    # 환불이면 revocationDate 우선
    ios_refund = {"data": {"transactionInfo": {"purchaseDate": 111, "revocationDate": ms}}}
    assert f("ios", ios_refund, "REFUND") == PAID_AT
    android_payload = {"eventTimeMillis": str(ms)}
    assert f("android", android_payload, "RENEWED") == PAID_AT
    # 값 없으면 None
    assert f("ios", {"data": {}}, "RENEWED") is None
    assert f("android", {}, "RENEWED") is None


# ─── subscription_service: 스토어 갱신 웹훅이 실제 결제시각으로 기록 ──────────

@pytest.mark.asyncio
async def test_store_renewal_records_real_paid_at(db):
    user = await _make_user(db)
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="android",
        amount=699, currency="USD", billing_interval="monthly",
        store_original_transaction_id="orig_tx_paidat",
        store_product_id="pro_monthly",
    )
    db.add(sub)
    await db.flush()

    ms = 1741608000000  # 2025-03-10 12:00 UTC
    await subscription_service.handle_store_event(
        platform="android",
        event_type="RENEWED",
        original_transaction_id="orig_tx_paidat",
        transaction_id="order_paidat_1",
        product_id="pro_monthly",
        expires_at=None,
        auto_renewing=True,
        raw_payload={"eventTimeMillis": str(ms)},
        db=db,
    )

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "order_paidat_1")
    )).scalar_one()
    _assert_same_instant(row.created_at, PAID_AT)


@pytest.mark.asyncio
async def test_store_renewal_without_timestamp_falls_back_to_now(db):
    """페이로드에 시각이 없으면 now() 기본값으로 폴백(크래시 X)."""
    user = await _make_user(db)
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="android",
        amount=699, currency="USD", billing_interval="monthly",
        store_original_transaction_id="orig_tx_nots",
        store_product_id="pro_monthly",
    )
    db.add(sub)
    await db.flush()

    await subscription_service.handle_store_event(
        platform="android",
        event_type="RENEWED",
        original_transaction_id="orig_tx_nots",
        transaction_id="order_nots_1",
        product_id="pro_monthly",
        expires_at=None,
        auto_renewing=True,
        raw_payload={},  # eventTimeMillis 없음
        db=db,
    )

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "order_nots_1")
    )).scalar_one()
    assert row.created_at is not None
    assert row.created_at.year >= 2026  # now() 폴백
