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

from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.services.subscription_service import (
    handle_store_event, activate_store_subscription,
    _record_payment_idempotent, _normalize_tx_id,
)


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
async def test_same_transaction_id_twice_is_idempotent(db):
    """같은 거래번호로 두 번 갱신 웹훅이 와도(재전송) 멱등하게 넘어간다.

    예전엔 같은 거래번호 두 번이면 유니크 인덱스에 걸려 IntegrityError가 나고
    웹훅 트랜잭션이 통째로 롤백 → 500이 떨어졌다. 이제 handle_store_event가
    사전 중복체크로 결제 행을 한 번만 넣고, 두 번째는 조용히 건너뛴다.
    Dodo(_handle_payment_succeeded)랑 같은 멱등 동작.
    """
    user, sub = await _make_android_sub(db)

    r1 = await _renew(db, PURCHASE_TOKEN, "GPA.same-order-id")
    await db.flush()

    # 재전송: 예외 없이 통과해야 하고, success 행은 여전히 1건
    r2 = await _renew(db, PURCHASE_TOKEN, "GPA.same-order-id")
    await db.flush()

    assert r1["status"] == "ok"
    assert r2["status"] == "ok"
    assert await _count_success(db, sub.id) == 1


@pytest.mark.asyncio
async def test_verify_retry_is_idempotent(db):
    """같은 거래로 verify를 두 번 호출해도(앱 재시도/중복 호출) 멱등하게 넘어간다.

    예전엔 activate_store_subscription이 결제 행을 생짜 db.add로 넣어서,
    같은 transaction_id로 verify가 두 번 오면 (platform, pg_transaction_id, status)
    유니크 인덱스에 걸려 IntegrityError → 500이 떨어졌다. 이제 _record_payment_idempotent로
    넣어서, 두 번째는 조용히 건너뛰고 success 행은 1건만 유지한다.
    """
    user = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4().hex[:10]}", plan="free")
    db.add(user)
    await db.flush()

    async def _verify():
        return await activate_store_subscription(
            user_id=user.id,
            platform="android",
            product_id="com.wewantpeace.pro_monthly",
            transaction_id="GPA.verify-retry-0001",
            original_transaction_id="tok_verify_retry",
            expires_at=None,
            auto_renewing=True,
            raw_response={"source": "verify"},
            db=db,
        )

    sub1 = await _verify()
    await db.flush()

    # 재시도: 예외 없이 통과해야 하고, success 행은 여전히 1건
    sub2 = await _verify()
    await db.flush()

    assert sub1.id == sub2.id  # 같은 구독을 갱신, 새로 안 만듦
    assert await _count_success(db, sub1.id) == 1


@pytest.mark.asyncio
async def test_refund_resend_is_idempotent(db):
    """환불 웹훅 재전송도 멱등 — refunded 행 1건 유지, 예외 없음."""
    user, sub = await _make_android_sub(db)

    async def _refund():
        return await handle_store_event(
            platform="android",
            event_type="REFUND",
            original_transaction_id=PURCHASE_TOKEN,
            transaction_id="GPA.refund-order-id",
            product_id="pro_monthly",
            expires_at=None,
            auto_renewing=False,
            raw_payload={"event": "REFUND"},
            db=db,
        )

    await _refund()
    await db.flush()
    await _refund()  # 재전송
    await db.flush()

    res = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.subscription_id == sub.id,
            PaymentHistory.status == "refunded",
        )
    )
    assert res.scalar_one() == 1


async def _revenue(db, sub_id) -> int:
    """매출 집계와 동일 기준 — status='success'인 결제행 amount 합."""
    res = await db.execute(
        select(func.coalesce(func.sum(PaymentHistory.amount), 0)).where(
            PaymentHistory.subscription_id == sub_id,
            PaymentHistory.status == "success",
        )
    )
    return res.scalar_one()


@pytest.mark.asyncio
async def test_store_refund_deducts_revenue(db):
    """스토어 환불이 들어오면 원결제 success 행이 refunded로 뒤집혀 매출에서 빠진다.

    매출(monthly_revenue)은 status='success' 행 amount 합이다. 예전엔 환불이 별도
    refunded 행만 추가하고 원 success 행을 그대로 둬서, 환불해도 매출이 안 줄었다
    (스토어 환불 매출 미반영 버그). dodo 환불처럼 원행을 뒤집어 매출에서 빠지게 한다.
    """
    user, sub = await _make_android_sub(db)

    # 원결제 1건(success) — orderId를 거래번호로
    await _renew(db, PURCHASE_TOKEN, "GPA.paid-order-1")
    await db.flush()
    assert await _revenue(db, sub.id) == 699  # 매출 잡힘

    # 같은 거래 환불
    await handle_store_event(
        platform="android",
        event_type="REFUND",
        original_transaction_id=PURCHASE_TOKEN,
        transaction_id="GPA.paid-order-1",
        product_id="pro_monthly",
        expires_at=None,
        auto_renewing=False,
        raw_payload={"event": "REFUND"},
        db=db,
    )
    await db.flush()

    # 매출에서 빠져야 한다(원 success 행이 refunded로 뒤집힘)
    assert await _revenue(db, sub.id) == 0
    # refunded 행은 1건, success 행은 0건 (행 중복 생성 없이 상태만 전환)
    assert await _count_success(db, sub.id) == 0
    refunded = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.subscription_id == sub.id,
            PaymentHistory.status == "refunded",
        )
    )
    assert refunded.scalar_one() == 1
    # 유저 등급 회수
    await db.refresh(user)
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_store_refund_resend_after_flip_is_idempotent(db):
    """원결제를 뒤집은 환불이 재전송돼도 refunded 행이 늘지 않는다."""
    user, sub = await _make_android_sub(db)
    await _renew(db, PURCHASE_TOKEN, "GPA.paid-order-2")
    await db.flush()

    async def _refund():
        return await handle_store_event(
            platform="android", event_type="REFUND",
            original_transaction_id=PURCHASE_TOKEN, transaction_id="GPA.paid-order-2",
            product_id="pro_monthly", expires_at=None, auto_renewing=False,
            raw_payload={"event": "REFUND"}, db=db,
        )

    await _refund()
    await db.flush()
    await _refund()  # 재전송
    await db.flush()

    assert await _revenue(db, sub.id) == 0
    refunded = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.subscription_id == sub.id,
            PaymentHistory.status == "refunded",
        )
    )
    assert refunded.scalar_one() == 1


@pytest.mark.asyncio
async def test_google_revoked_deducts_revenue_and_downgrades(db):
    """구글 RTDN REVOKED(타입 12, 환불성 회수)도 매출 차감 + 등급 회수된다.

    예전엔 'REVOKED'가 취소 그룹('REVOKE')과 철자가 달라 어디에도 안 걸려 무시됐다.
    그 결과 환불됐는데도 구독이 active로 남고(유저 pro 유지) 원결제가 매출에 그대로 남았다.
    """
    user, sub = await _make_android_sub(db)
    await _renew(db, PURCHASE_TOKEN, "GPA.paid-order-3")
    await db.flush()
    assert await _revenue(db, sub.id) == 699

    res = await handle_store_event(
        platform="android", event_type="REVOKED",
        original_transaction_id=PURCHASE_TOKEN, transaction_id="GPA.paid-order-3",
        product_id="pro_monthly", expires_at=None, auto_renewing=False,
        raw_payload={"event": "REVOKED"}, db=db,
    )
    await db.flush()

    assert res["status"] == "ok"  # 무시되지 않고 처리됨
    assert await _revenue(db, sub.id) == 0
    await db.refresh(sub)
    await db.refresh(user)
    assert sub.status == "expired"
    assert user.plan == "free"


def test_normalize_tx_id_service():
    """서비스 레이어 정규화도 빈/공백을 None으로 통일한다."""
    assert _normalize_tx_id(None) is None
    assert _normalize_tx_id("") is None
    assert _normalize_tx_id("   ") is None
    assert _normalize_tx_id("GPA.1") == "GPA.1"
    assert _normalize_tx_id("  GPA.1  ") == "GPA.1"


@pytest.mark.asyncio
async def test_empty_tx_id_renewals_stored_as_null_not_collapsed(db):
    """tx id가 빈 문자열인 갱신 결제는 NULL로 저장돼 서로 충돌하지 않는다.

    빈 문자열 ''을 그대로 저장하면 부분 유니크 인덱스(WHERE pg_transaction_id
    IS NOT NULL)가 ''을 '진짜 키'로 잡아서, tx id 없는 서로 다른 갱신 결제 두 건이
    같은 '' 키로 충돌(IntegrityError → 500)하거나 두 번째가 통째로 막혔다.
    정규화로 ''→None을 만들면 인덱스가 무시(IS NULL)해서 둘 다 멀쩡히 보존된다.
    """
    user, sub = await _make_android_sub(db)

    # 빈 문자열 tx id로 두 번 적재 — 둘 다 NULL로 들어가고 충돌 없어야 함
    ok1 = await _record_payment_idempotent(
        db, user_id=user.id, subscription_id=sub.id, amount=699,
        status="success", platform="android", pg_transaction_id="",
        pg_response={"src": "renew-1"},
    )
    await db.flush()
    ok2 = await _record_payment_idempotent(
        db, user_id=user.id, subscription_id=sub.id, amount=699,
        status="success", platform="android", pg_transaction_id="   ",
        pg_response={"src": "renew-2"},
    )
    await db.flush()

    assert ok1 is True
    assert ok2 is True
    assert await _count_success(db, sub.id) == 2

    # 저장된 tx id는 빈 문자열이 아니라 NULL이어야 한다
    res = await db.execute(
        select(PaymentHistory.pg_transaction_id).where(
            PaymentHistory.subscription_id == sub.id
        )
    )
    assert all(r[0] is None for r in res.all())
