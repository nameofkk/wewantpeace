"""google_verify(앱 영수증 검증 엔드포인트)가 결제 거래번호로 구글 orderId를 쓰는지 검증.

배경:
purchase_token은 구독이 갱신돼도 내내 같은 값이라, 갱신 검증마다 같은 값이
payment_history.pg_transaction_id에 들어가 (platform, pg_transaction_id, status)
부분 유니크 인덱스에 충돌했다. RTDN 웹훅은 이미 orderId로 고쳐졌지만, 앱이 직접
호출하는 /google/verify 엔드포인트는 아직 purchase_token을 그대로 쓰고 있었다.

이 테스트는:
- transaction_id(결제 거래번호) = result.order_id (200자로 컷)
- original_transaction_id(구독 조회 키) = purchase_token (256자로 컷, 그대로)
- order_id가 없으면 purchase_token으로 폴백
을 못박는다.
"""
import uuid

import pytest
from sqlalchemy import select

import backend.app.services.google_play_billing as gpb
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.routers.store_subscriptions import google_verify, GoogleVerifyBody


PRODUCT_ID = "com.wewantpeace.pro_monthly"
PURCHASE_TOKEN = "tok_android_stable_0001"


def _patch_billing(monkeypatch, result):
    """verify_subscription / acknowledge_subscription 목 주입."""
    async def _fake_verify(package_name, purchase_token):
        return result

    async def _fake_ack(package_name, product_id, purchase_token):
        return True

    monkeypatch.setattr(gpb, "verify_subscription", _fake_verify)
    monkeypatch.setattr(gpb, "acknowledge_subscription", _fake_ack)


async def _make_user(db) -> User:
    user = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(user)
    await db.flush()
    return user


async def _tx_for_sub(db, sub_id):
    res = await db.execute(
        select(PaymentHistory.pg_transaction_id).where(
            PaymentHistory.subscription_id == sub_id
        )
    )
    return [r[0] for r in res.all()]


@pytest.mark.asyncio
async def test_verify_uses_order_id_as_transaction_id(db, monkeypatch):
    """orderId가 있으면 결제 거래번호로 orderId를 쓰고, 구독 조회 키는 토큰을 쓴다."""
    user = await _make_user(db)
    _patch_billing(monkeypatch, {
        "valid": True,
        "acknowledgement_state": 1,
        "order_id": "GPA.3300-1111-2222-33333..0",
        "expiry_time": "",
        "auto_renewing": True,
        "raw": {"src": "verify"},
    })

    body = GoogleVerifyBody(purchase_token=PURCHASE_TOKEN, product_id=PRODUCT_ID)
    await google_verify(body=body, current_user=user, db=db)
    await db.flush()

    # 구독 조회 키(original)는 purchase_token 그대로여야 갱신 매칭이 된다
    sub = (await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )).scalar_one()
    assert sub.store_original_transaction_id == PURCHASE_TOKEN
    # 거래번호는 orderId
    assert sub.store_transaction_id == "GPA.3300-1111-2222-33333..0"

    # payment_history에도 orderId가 거래번호로 적재됐는지
    assert await _tx_for_sub(db, sub.id) == ["GPA.3300-1111-2222-33333..0"]


@pytest.mark.asyncio
async def test_verify_falls_back_to_token_when_no_order_id(db, monkeypatch):
    """orderId가 비면 purchase_token으로 폴백한다 (거래번호 NULL 방지)."""
    user = await _make_user(db)
    _patch_billing(monkeypatch, {
        "valid": True,
        "acknowledgement_state": 1,
        "order_id": "",  # 없음
        "expiry_time": "",
        "auto_renewing": True,
        "raw": {},
    })

    body = GoogleVerifyBody(purchase_token=PURCHASE_TOKEN, product_id=PRODUCT_ID)
    await google_verify(body=body, current_user=user, db=db)
    await db.flush()

    sub = (await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )).scalar_one()
    assert sub.store_transaction_id == PURCHASE_TOKEN
    assert await _tx_for_sub(db, sub.id) == [PURCHASE_TOKEN]


@pytest.mark.asyncio
async def test_verify_two_renewals_distinct_order_ids_no_conflict(db, monkeypatch):
    """앱이 같은 토큰으로 갱신 검증을 두 번(다른 orderId) 보내도 충돌 없이 둘 다 쌓인다."""
    user = await _make_user(db)
    body = GoogleVerifyBody(purchase_token=PURCHASE_TOKEN, product_id=PRODUCT_ID)

    _patch_billing(monkeypatch, {
        "valid": True, "acknowledgement_state": 1,
        "order_id": "GPA.order..A", "expiry_time": "", "auto_renewing": True, "raw": {},
    })
    sub1 = await google_verify(body=body, current_user=user, db=db)
    await db.flush()

    _patch_billing(monkeypatch, {
        "valid": True, "acknowledgement_state": 1,
        "order_id": "GPA.order..B", "expiry_time": "", "auto_renewing": True, "raw": {},
    })
    await google_verify(body=body, current_user=user, db=db)
    await db.flush()

    sub = (await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )).scalar_one()
    # 같은 구독 하나, 결제 행은 서로 다른 orderId 2건
    txns = sorted(await _tx_for_sub(db, sub.id))
    assert txns == ["GPA.order..A", "GPA.order..B"]
