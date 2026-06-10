"""payment_history 중복 적재 방지 테스트.

웹훅 재전송 / sync 백필이 같은 결제를 두 번 적재해서 매출이 부풀려지던 버그 방지:
1. (platform, pg_transaction_id, status) 부분 유니크 인덱스가 같은 success 행 두 번을 막는지
2. _handle_payment_succeeded 의 멱등성 가드가 이미 기록된 결제를 건너뛰는지
3. success → refunded 처럼 status가 다르면 같은 거래라도 허용되는지
4. pg_transaction_id 가 NULL 인 행은 여러 개 허용되는지
"""
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.routers import dodopayments


async def _make_user(db) -> User:
    u = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(u)
    await db.flush()
    return u


async def _count_history(db, payment_id: str) -> int:
    res = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.pg_transaction_id == payment_id
        )
    )
    return res.scalar_one()


@pytest.mark.asyncio
async def test_unique_index_blocks_duplicate_success(db):
    """같은 (platform, pg_transaction_id, status=success) 두 번 적재는 DB가 막는다."""
    user = await _make_user(db)
    common = dict(
        user_id=user.id, amount=699, currency="USD",
        status="success", platform="dodopayments", pg_transaction_id="pay_dup_1",
    )
    db.add(PaymentHistory(**common))
    await db.flush()

    db.add(PaymentHistory(**common))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_refund_of_same_txn_allowed(db):
    """같은 거래라도 status가 success/refunded로 다르면 둘 다 허용."""
    user = await _make_user(db)
    db.add(PaymentHistory(
        user_id=user.id, amount=699, currency="USD",
        status="success", platform="dodopayments", pg_transaction_id="pay_ref_1",
    ))
    db.add(PaymentHistory(
        user_id=user.id, amount=699, currency="USD",
        status="refunded", platform="dodopayments", pg_transaction_id="pay_ref_1",
    ))
    await db.flush()  # 예외 없이 통과해야 함
    assert await _count_history(db, "pay_ref_1") == 2


@pytest.mark.asyncio
async def test_null_txn_id_allows_multiple(db):
    """pg_transaction_id 가 NULL 인 내부/레거시 기록은 여러 개 허용."""
    user = await _make_user(db)
    for _ in range(3):
        db.add(PaymentHistory(
            user_id=user.id, amount=100, currency="USD",
            status="success", platform="web", pg_transaction_id=None,
        ))
    await db.flush()  # NULL은 서로 구별되므로 통과


@pytest.mark.asyncio
async def test_handler_skips_already_recorded_payment(db):
    """웹훅 재전송: 이미 success로 적재된 payment_id는 핸들러가 건너뛴다."""
    user = await _make_user(db)
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="dodopayments",
        amount=699, currency="USD", billing_interval="monthly",
        dodo_subscription_id="dodo_sub_x",
    )
    db.add(sub)
    await db.flush()

    data = SimpleNamespace(
        payment_id="pay_resend_1",
        subscription_id="dodo_sub_x",
        total_amount=699,
        currency="USD",
    )

    # 1차: 정상 적재
    await dodopayments._handle_payment_succeeded(data, db)
    assert await _count_history(db, "pay_resend_1") == 1

    # 2차(재전송): 멱등 가드로 건너뜀 → 여전히 1건
    await dodopayments._handle_payment_succeeded(data, db)
    assert await _count_history(db, "pay_resend_1") == 1


@pytest.mark.asyncio
async def test_payment_already_recorded_helper(db):
    """_payment_already_recorded 헬퍼 단위 검증."""
    user = await _make_user(db)
    assert await dodopayments._payment_already_recorded(db, "pay_helper_1") is False
    assert await dodopayments._payment_already_recorded(db, None) is False

    db.add(PaymentHistory(
        user_id=user.id, amount=699, currency="USD",
        status="success", platform="dodopayments", pg_transaction_id="pay_helper_1",
    ))
    await db.flush()
    assert await dodopayments._payment_already_recorded(db, "pay_helper_1") is True
