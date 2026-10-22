"""구글 '자동 갱신 끔(CANCELED)'은 만료가 아니다 — 이미 낸 기간까지는 써야 한다.

배경 (2026-10-10 운영):
슬로베니아 손님이 Pro+ 월간(EUR 10.99)을 결제하고 2분 뒤 자동 갱신만 껐다. 구글 상태는
SUBSCRIPTION_STATE_CANCELED, 만료일 11-10. 그런데 verify_subscription 이 CANCELED 를 무효로 보고
sync_store_subscriptions 가 결제 2시간 뒤 구독을 expired 로, 다음 날 새벽 회원을 free 로 내렸다.
같은 무렵 무료 체험 시작(ETB 0)은 $6.99 결제로 적혔다.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import backend.app.services.google_play_billing as gpb
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.subscription_service import handle_store_event, activate_store_subscription

TOKEN = "tok_cancel_keeps_access_0001"


def _google_response(state, expiry, offer_id=None, order_id="GPA.3340-6148-4777-99938", offer_phase=None):
    item = {"productId": "com.wewantpeace.proplus_monthly", "expiryTime": expiry,
            "offerDetails": {"basePlanId": "wewantpeaceproplus", **({"offerId": offer_id} if offer_id else {})}}
    if offer_phase is not None:
        item["offerPhase"] = offer_phase
    return {"subscriptionState": state, "lineItems": [item], "latestOrderId": order_id,
            "acknowledgementState": "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
            "canceledStateContext": {"userInitiatedCancellation": {"cancelTime": "2026-10-10T09:58:28.735Z"}}}


class _FakeService:
    def __init__(self, resp):
        self.resp = resp

    def purchases(self):
        return self

    def subscriptionsv2(self):
        return self

    def get(self, **_):
        return self

    def execute(self):
        return self.resp


async def _parse(monkeypatch, resp):
    monkeypatch.setattr(gpb, "_get_android_publisher_service", lambda: _FakeService(resp))
    return await gpb.verify_subscription("com.wewantpeace.app", TOKEN)


@pytest.mark.asyncio
async def test_canceled_with_future_expiry_is_still_valid(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat().replace("+00:00", "Z")
    r = await _parse(monkeypatch, _google_response("SUBSCRIPTION_STATE_CANCELED", future))
    assert r["valid"] is True and r["canceled"] is True
    assert r["cancel_time"] == "2026-10-10T09:58:28.735Z"


@pytest.mark.asyncio
async def test_canceled_after_expiry_is_not_valid(monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    r = await _parse(monkeypatch, _google_response("SUBSCRIPTION_STATE_CANCELED", past))
    assert r["valid"] is False


@pytest.mark.asyncio
async def test_free_trial_detection(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    # offerPhase 없음: 체험 혜택으로 산 첫 주기면 체험
    r = await _parse(monkeypatch, _google_response("SUBSCRIPTION_STATE_ACTIVE", future, offer_id="pro-free-trial",
                                                   order_id="GPA.3388-7018-3316-92374"))
    assert r["in_free_trial"] is True
    # 체험이 끝나 첫 갱신 주문(..0)이 생긴 뒤에는 offerId 가 남아 있어도 유료
    r = await _parse(monkeypatch, _google_response("SUBSCRIPTION_STATE_ACTIVE", future, offer_id="pro-free-trial",
                                                   order_id="GPA.3388-7018-3316-92374..0"))
    assert r["in_free_trial"] is False
    # offerPhase 가 있으면 그걸 따른다
    r = await _parse(monkeypatch, _google_response("SUBSCRIPTION_STATE_ACTIVE", future, offer_id="pro-free-trial",
                                                   offer_phase={"basePrice": {}}))
    assert r["in_free_trial"] is False


async def _paid_sub(db):
    user = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="pro_plus")
    db.add(user)
    await db.flush()
    sub = Subscription(user_id=user.id, plan="pro_plus", status="active", platform="android", amount=999,
                       store_product_id="com.wewantpeace.proplus_monthly", store_transaction_id="GPA.x",
                       store_original_transaction_id=TOKEN, auto_renewing=True,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.add(sub)
    await db.flush()
    return user, sub


@pytest.mark.asyncio
async def test_canceled_webhook_keeps_plan_until_expiry(db):
    user, sub = await _paid_sub(db)
    await handle_store_event(platform="android", event_type="CANCELED", original_transaction_id=TOKEN,
                             transaction_id="GPA.x", product_id="com.wewantpeace.proplus_monthly",
                             expires_at=sub.expires_at, auto_renewing=False, raw_payload={}, db=db)
    await db.flush()
    assert sub.status == "cancelled" and sub.auto_renewing is False and sub.cancelled_at is not None
    assert user.plan == "pro_plus"


@pytest.mark.asyncio
async def test_canceled_webhook_after_expiry_still_expires(db):
    user, sub = await _paid_sub(db)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    await handle_store_event(platform="android", event_type="CANCELED", original_transaction_id=TOKEN,
                             transaction_id="GPA.x", product_id="com.wewantpeace.proplus_monthly",
                             expires_at=past, auto_renewing=False, raw_payload={}, db=db)
    await db.flush()
    assert sub.status == "expired" and user.plan == "free"


@pytest.mark.asyncio
async def test_free_trial_start_is_not_recorded_as_payment(db):
    user = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(user)
    await db.flush()
    sub = await activate_store_subscription(
        user_id=user.id, platform="android", product_id="com.wewantpeace.pro_monthly",
        transaction_id="GPA.trial-0001", original_transaction_id="tok_trial_0001",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7), auto_renewing=True,
        raw_response={}, db=db, is_trial=True,
    )
    await db.flush()
    paid = (await db.execute(select(func.count()).select_from(PaymentHistory)
                             .where(PaymentHistory.subscription_id == sub.id))).scalar_one()
    assert paid == 0
    assert sub.status == "trial" and sub.trial_end is not None
    assert user.plan == "pro"
