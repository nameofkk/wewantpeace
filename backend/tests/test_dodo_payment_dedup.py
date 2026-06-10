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


async def _make_paid_sub(db, *, amount=699, payment_id="pay_x", plan="pro"):
    """user + active sub + success PaymentHistory 한 세트 생성."""
    user = await _make_user(db)
    user.plan = plan
    sub = Subscription(
        user_id=user.id, plan=plan, status="active", platform="dodopayments",
        amount=amount, currency="USD", billing_interval="monthly",
        dodo_subscription_id=f"dsub-{uuid.uuid4().hex[:8]}",
    )
    db.add(sub)
    await db.flush()
    hist = PaymentHistory(
        user_id=user.id, subscription_id=sub.id, amount=amount, currency="USD",
        status="success", platform="dodopayments", pg_transaction_id=payment_id,
    )
    db.add(hist)
    await db.flush()
    return user, sub, hist


@pytest.mark.asyncio
async def test_refund_full_marks_refunded_and_revokes(db):
    """전액 환불: success → refunded, 구독 expired, user.plan free."""
    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_full_1")

    data = SimpleNamespace(payment_id="pay_full_1", amount=699)
    await dodopayments._handle_refund_succeeded(data, db)

    await db.refresh(hist)
    await db.refresh(sub)
    await db.refresh(user)
    assert hist.status == "refunded"
    assert hist.amount == 699  # 금액은 그대로, 상태만 바뀜
    assert sub.status == "expired"
    assert sub.auto_renewing is False
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_refund_no_amount_treated_as_full(db):
    """amount 없는 환불 이벤트는 전액 환불로 본다."""
    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_noamt_1")

    data = SimpleNamespace(payment_id="pay_noamt_1", amount=None)
    await dodopayments._handle_refund_succeeded(data, db)

    await db.refresh(hist)
    await db.refresh(user)
    assert hist.status == "refunded"
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_refund_partial_reduces_amount_keeps_access(db):
    """부분 환불: 매출에서 환불액만 차감, 등급 유지."""
    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_part_1")

    data = SimpleNamespace(payment_id="pay_part_1", amount=200)
    await dodopayments._handle_refund_succeeded(data, db)

    await db.refresh(hist)
    await db.refresh(sub)
    await db.refresh(user)
    assert hist.status == "success"   # 여전히 매출에 잡힘
    assert hist.amount == 499         # 699 - 200
    assert sub.status == "active"     # 등급 유지
    assert user.plan == "pro"


@pytest.mark.asyncio
async def test_refund_idempotent(db):
    """환불 웹훅 재전송: 두 번 와도 refunded 1건 유지, 예외 없음."""
    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_idem_1")
    data = SimpleNamespace(payment_id="pay_idem_1", amount=699)

    await dodopayments._handle_refund_succeeded(data, db)
    await dodopayments._handle_refund_succeeded(data, db)  # 재전송

    res = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.pg_transaction_id == "pay_idem_1",
            PaymentHistory.status == "refunded",
        )
    )
    assert res.scalar_one() == 1
    # success 행은 남아있지 않아야 매출에서 빠진다
    res2 = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.pg_transaction_id == "pay_idem_1",
            PaymentHistory.status == "success",
        )
    )
    assert res2.scalar_one() == 0


@pytest.mark.asyncio
async def test_refund_missing_original_no_crash(db):
    """원결제 기록이 없는 환불 이벤트는 조용히 넘어간다(크래시 X)."""
    data = SimpleNamespace(payment_id="pay_ghost_1", amount=699)
    await dodopayments._handle_refund_succeeded(data, db)  # 예외 없이 통과
    assert await _count_history(db, "pay_ghost_1") == 0


@pytest.mark.asyncio
async def test_refund_revenue_excludes_refunded(db):
    """매출 집계(success amount 합)가 환불 반영을 정확히 한다."""
    # 전액 환불 1건 + 부분 환불 1건 + 멀쩡한 결제 1건
    await _make_paid_sub(db, amount=699, payment_id="rev_full")
    await _make_paid_sub(db, amount=699, payment_id="rev_part")
    await _make_paid_sub(db, amount=699, payment_id="rev_ok")

    await dodopayments._handle_refund_succeeded(
        SimpleNamespace(payment_id="rev_full", amount=699), db)
    await dodopayments._handle_refund_succeeded(
        SimpleNamespace(payment_id="rev_part", amount=300), db)

    total = await db.execute(
        select(func.coalesce(func.sum(PaymentHistory.amount), 0)).where(
            PaymentHistory.status == "success"
        )
    )
    # rev_full 전액 빠짐(0), rev_part 300 차감(399), rev_ok 그대로(699) → 1098
    assert total.scalar_one() == 399 + 699


@pytest.mark.asyncio
async def test_backfill_updates_existing_success_to_refunded(db):
    """admin 백필: 이미 success로 있던 결제가 Dodo에서 refunded로 오면 갱신(스킵 X)."""
    from backend.app.routers.admin import _backfill_payment_candidates

    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_bf_1")

    # Dodo가 같은 결제를 이제 refunded로 보고함
    dodo_payment = SimpleNamespace(
        payment_id="pay_bf_1", total_amount=699, currency="USD",
        created_at=hist.created_at,
    )
    candidates = [(dodo_payment, sub, "refunded")]

    backfilled, refunded = await _backfill_payment_candidates(db, candidates)
    await db.flush()

    assert (backfilled, refunded) == (0, 1)
    await db.refresh(hist)
    assert hist.status == "refunded"
    # success 행이 더는 없어야 매출에서 빠진다
    res = await db.execute(
        select(func.count()).select_from(PaymentHistory).where(
            PaymentHistory.pg_transaction_id == "pay_bf_1",
            PaymentHistory.status == "success",
        )
    )
    assert res.scalar_one() == 0


@pytest.mark.asyncio
async def test_backfill_skips_true_duplicate(db):
    """admin 백필: 같은 상태로 이미 있으면 진짜 중복 → 새로 안 넣음."""
    from backend.app.routers.admin import _backfill_payment_candidates

    user, sub, hist = await _make_paid_sub(db, amount=699, payment_id="pay_bf_2")
    dodo_payment = SimpleNamespace(
        payment_id="pay_bf_2", total_amount=699, currency="USD",
        created_at=hist.created_at,
    )
    candidates = [(dodo_payment, sub, "success")]

    backfilled, refunded = await _backfill_payment_candidates(db, candidates)
    assert (backfilled, refunded) == (0, 0)
    assert await _count_history(db, "pay_bf_2") == 1


@pytest.mark.asyncio
async def test_backfill_inserts_new_refund_when_no_success(db):
    """admin 백필: success 기록이 아예 없던 결제가 refunded로 오면 새 행으로 적재."""
    from backend.app.routers.admin import _backfill_payment_candidates

    user = await _make_user(db)
    sub = Subscription(
        user_id=user.id, plan="pro", status="active", platform="dodopayments",
        amount=699, currency="USD", billing_interval="monthly",
        dodo_subscription_id="dsub-new",
    )
    db.add(sub)
    await db.flush()

    dodo_payment = SimpleNamespace(
        payment_id="pay_bf_3", total_amount=699, currency="USD",
        created_at=user.created_at,
    )
    candidates = [(dodo_payment, sub, "refunded")]

    backfilled, refunded = await _backfill_payment_candidates(db, candidates)
    await db.flush()
    assert (backfilled, refunded) == (1, 0)
    res = await db.execute(
        select(PaymentHistory.status).where(PaymentHistory.pg_transaction_id == "pay_bf_3")
    )
    assert res.scalar_one() == "refunded"


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
