"""금액 매핑 누락 가드 검증.

GOOGLE_PRODUCTS/APPLE_PRODUCTS엔 plan이 매핑돼 있는데 PLAN_AMOUNTS엔 그 plan의
금액이 빠져 있으면(미래 상품을 매핑에만 추가하고 금액 표를 깜빡한 경우),
예전엔 PLAN_AMOUNTS.get(plan, 0)이 0원짜리 success를 조용히 박아서 매출이 샜다.
이제는 amount가 None이면 ValueError로 큰 소리로 터뜨려서 0원 적재를 원천 차단한다.
"""
import uuid

import pytest
from sqlalchemy import select

from backend.app.core import store_products
from backend.app.models.user import User
from backend.app.models.subscription import PaymentHistory
from backend.app.services import subscription_service


async def _make_user(db) -> User:
    u = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_missing_plan_amount_raises_and_records_nothing(db, monkeypatch):
    """매핑은 됐는데 금액이 없는 미래 상품 → ValueError, 0원 결제 적재 X."""
    user = await _make_user(db)

    # 미래 상품: GOOGLE_PRODUCTS엔 추가됐지만 PLAN_AMOUNTS엔 금액이 없다.
    future_product = "com.wewantpeace.pro_quarterly"
    future_plan = "pro_quarterly"
    monkeypatch.setitem(store_products.GOOGLE_PRODUCTS, future_product, future_plan)
    # PLAN_AMOUNTS엔 일부러 안 넣는다.
    assert future_plan not in store_products.PLAN_AMOUNTS

    with pytest.raises(ValueError, match="PLAN_AMOUNTS"):
        await subscription_service.activate_store_subscription(
            user_id=user.id,
            platform="android",
            product_id=future_product,
            transaction_id="tx_future_1",
            original_transaction_id=None,
            expires_at=None,
            auto_renewing=True,
            raw_response={},
            db=db,
        )

    # 0원짜리 success가 단 한 건도 박히면 안 된다.
    rows = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "tx_future_1")
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_known_plan_records_correct_amount(db):
    """금액이 매핑된 정상 상품은 그대로 올바른 금액으로 적재된다(회귀 방지)."""
    user = await _make_user(db)

    sub = await subscription_service.activate_store_subscription(
        user_id=user.id,
        platform="android",
        product_id="com.wewantpeace.pro_monthly",  # → pro, 699
        transaction_id="tx_ok_1",
        original_transaction_id=None,
        expires_at=None,
        auto_renewing=True,
        raw_response={},
        db=db,
    )
    assert sub.amount == store_products.PLAN_AMOUNTS["pro"] == 699

    row = (await db.execute(
        select(PaymentHistory).where(PaymentHistory.pg_transaction_id == "tx_ok_1")
    )).scalar_one()
    assert row.amount == 699
    assert row.status == "success"
