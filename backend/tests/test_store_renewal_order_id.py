"""안드로이드 구독 갱신 시 결제 거래번호를 구글 orderId로 쓰는지 검증.

배경:
purchase_token은 구독이 갱신돼도 내내 같은 값이라, 갱신 결제마다 payment_history의
pg_transaction_id에 같은 값이 들어가서 (platform, pg_transaction_id, status) 부분
유니크 인덱스에 충돌했다. 갱신마다 새로 발급되는 구글 orderId를 거래번호로 쓰면 충돌이
사라진다.
"""
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.subscription_service import handle_store_event


PURCHASE_TOKEN = "tok_android_stable_0001"


async def _make_android_sub(db) -> tuple[User, Subscription]:
    user = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="pro")
    db.add(user)
    await db.flush()
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="android",
        amount=699, currency="USD", billing_interval="monthly",
        store_product_id="pro_monthly",
        store_transaction_id=PURCHASE_TOKEN,
        store_original_transaction_id=PURCHASE_TOKEN,
        auto_renewing=True,
    )
    db.add(sub)
    await db.flush()
    return user, sub


async def _renew(db, sub_lookup_key: str, transaction_id: str):
    """RENEWED 웹훅 한 번 처리."""
    return await handle_store_event(
        platform="android",
        event_type="RENEWED",
        original_transaction_id=sub_lookup_key,
        transaction_id=transaction_id,
        product_id="pro_monthly",
        expires_at=None,
        auto_renewing=True,
        raw_payload={"event": "RENEWED"},
        db=db,
    )


async def _count_success(db, sub_id) -> int:
    res = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.subscription_id == sub_id,
            PaymentHistory.status == "success",
        )
    )
    return res.scalar_one()


@pytest.mark.asyncio
async def test_renewals_with_distinct_order_ids_do_not_conflict(db):
    """갱신마다 다른 orderId를 거래번호로 쓰면 결제 행이 충돌 없이 쌓인다."""
    user, sub = await _make_android_sub(db)

    # 구독 조회 키는 늘 purchase_token, 거래번호는 갱신마다 다른 orderId
    await _renew(db, PURCHASE_TOKEN, "GPA.3300-1111-2222-33333..0")
    await db.flush()
    await _renew(db, PURCHASE_TOKEN, "GPA.3300-1111-2222-33333..1")
    await db.flush()
    await _renew(db, PURCHASE_TOKEN, "GPA.3300-1111-2222-33333..2")
    await db.flush()

    assert await _count_success(db, sub.id) == 3

    # 거래번호가 실제 orderId로 들어갔는지 확인
    res = await db.execute(
        select(PaymentHistory.pg_transaction_id).where(
            PaymentHistory.subscription_id == sub.id
        ).order_by(PaymentHistory.created_at.asc())
    )
    txns = [r[0] for r in res.all()]
    assert txns == [
        "GPA.3300-1111-2222-33333..0",
        "GPA.3300-1111-2222-33333..1",
        "GPA.3300-1111-2222-33333..2",
    ]


@pytest.mark.asyncio
async def test_same_transaction_id_twice_still_conflicts(db):
    """회귀 가드: 같은 거래번호로 두 번 갱신하면 유니크 인덱스가 막는다.

    이게 바로 purchase_token을 그대로 쓰던 옛날 버그의 재현이다.
    orderId를 써야 하는 이유를 못 박아둔다.
    """
    user, sub = await _make_android_sub(db)

    await _renew(db, PURCHASE_TOKEN, "GPA.same-order-id")
    await db.flush()

    with pytest.raises(IntegrityError):
        await _renew(db, PURCHASE_TOKEN, "GPA.same-order-id")
        await db.flush()
