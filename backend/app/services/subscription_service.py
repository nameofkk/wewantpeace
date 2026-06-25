"""플랫폼 통합 구독 관리 서비스 레이어."""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.models.user import User
from backend.app.core.store_products import (
    google_product_to_plan, apple_product_to_plan, PLAN_AMOUNTS,
)
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)


def _parse_store_timestamp(value) -> datetime | None:
    """스토어 웹훅의 시각 값을 timezone-aware datetime으로 파싱한다.

    구글/애플은 시각을 밀리초 epoch 정수(또는 그 문자열)나 ISO8601 문자열로 준다.
    파싱 실패하거나 값이 없으면 None을 돌려서 호출부가 now() 기본값으로 폴백하게 한다.
    """
    if value is None:
        return None
    # 밀리초 epoch (int 또는 숫자 문자열)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            try:
                return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _store_event_paid_at(platform: str, raw_payload: dict, event_type: str) -> datetime | None:
    """스토어 웹훅 페이로드에서 실제 결제(이벤트 발생) 시각을 뽑는다.

    PaymentHistory.created_at에 '처리 시각'(DB now) 대신 실제 결제시각을 넣어서,
    웹훅이 늦게 도착해도 매출 집계 날짜가 안 밀리게 한다. 못 뽑으면 None → now() 폴백.

    애플(V2): data.transactionInfo.purchaseDate(ms)가 그 거래의 결제시각.
              환불이면 revocationDate(ms)를 우선 사용.
    구글(RTDN): pubsub 메시지의 eventTimeMillis(ms)가 알림(=갱신/결제) 발생 시각.
    """
    if not isinstance(raw_payload, dict):
        return None
    if platform == "ios":
        tx_info = (raw_payload.get("data") or {}).get("transactionInfo") or {}
        if event_type == "REFUND":
            return _parse_store_timestamp(
                tx_info.get("revocationDate") or tx_info.get("purchaseDate")
            )
        return _parse_store_timestamp(tx_info.get("purchaseDate"))
    if platform == "android":
        return _parse_store_timestamp(raw_payload.get("eventTimeMillis"))
    return None


def _normalize_tx_id(pg_transaction_id: str | None) -> str | None:
    """tx id를 정규화한다 — 빈 문자열·공백만 있는 값은 전부 None 하나로 모은다.

    멱등 키로 못 쓰는 값('', '   ', None)을 None 한 가지로 통일하는 이유:
    payment_history엔 (platform, pg_transaction_id, status) 부분 유니크 인덱스가
    'WHERE pg_transaction_id IS NOT NULL'로 걸려 있다. 그런데 빈 문자열 ''은 NULL이
    아니라서 인덱스가 '진짜 키'로 잡는다. 그러면 tx id 없이 들어오는 서로 다른 갱신
    결제들이 전부 같은 '' 키로 충돌해서, 멱등 사전체크는 스킵되는데(아래 not 가드) DB
    인덱스는 막아버리는 엇갈린 상태가 된다. 정규화로 ''→None을 만들어서 '키 없는 결제'는
    인덱스에서도 일관되게 빠지게(IS NULL) 하고, 멱등 체크도 똑같이 스킵되게 맞춘다.
    """
    if pg_transaction_id is None:
        return None
    stripped = pg_transaction_id.strip()
    return stripped or None


async def _payment_already_recorded(
    db: AsyncSession, platform: str, pg_transaction_id: str | None, status: str
) -> bool:
    """이 거래(platform + pg_transaction_id + status)가 이미 적재됐는지 확인.

    스토어 웹훅은 재전송이 흔하고(구글/애플 둘 다 ack 못 받으면 같은 갱신 알림을 또 보냄),
    sync 백필이랑도 겹친다. payment_history엔 (platform, pg_transaction_id, status)
    부분 유니크 인덱스가 걸려 있어서, 같은 거래를 두 번 넣으려 하면 IntegrityError가 나고
    웹훅 처리 트랜잭션이 통째로 롤백돼서 500이 떨어진다. 그걸 사전에 막는 1차 방어선.
    """
    pg_transaction_id = _normalize_tx_id(pg_transaction_id)
    if not pg_transaction_id:
        return False
    result = await db.execute(
        select(PaymentHistory.id).where(
            PaymentHistory.platform == platform,
            PaymentHistory.pg_transaction_id == pg_transaction_id,
            PaymentHistory.status == status,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _record_payment_idempotent(
    db: AsyncSession,
    *,
    user_id,
    subscription_id,
    amount,
    status: str,
    platform: str,
    pg_transaction_id: str | None,
    pg_response: dict,
    paid_at: datetime | None = None,
) -> bool:
    """PaymentHistory를 멱등하게 적재. 이미 있으면(또는 경합으로 막히면) 조용히 건너뜀.

    Dodo(dodopayments.py)랑 같은 2단 방어:
    1) 사전 중복체크 — 같은 거래가 이미 들어가 있으면 insert 자체를 안 한다.
    2) savepoint(begin_nested)로 감싼 insert — 사전 체크를 둘 다 통과한 동시 웹훅 경합으로
       유니크 인덱스가 걸려도 IntegrityError만 savepoint 안에서 롤백되고, 바깥 트랜잭션은
       살아남는다. 갱신 알림이 500 안 내고 멱등하게 넘어가게 하는 최종 방어선.

    paid_at는 실제 결제(이벤트) 시각. 주면 PaymentHistory.created_at에 그대로 박아서
    매출 집계가 '처리 시각'이 아닌 '실제 결제시각' 기준이 되게 한다. None이면 모델 기본값
    (now())이 적용된다.

    적재했으면 True, 중복이라 건너뛰었으면 False.
    """
    # 빈/공백 tx id는 None으로 정규화 — 멱등 사전체크와 DB 부분 유니크 인덱스가
    # '키 없는 결제'를 똑같이(IS NULL) 취급하게 맞춰서, tx id 빠진 갱신 결제가
    # 인덱스에 '' 키로 충돌하거나 매출이 부풀려지는 엇갈린 상태를 막는다.
    pg_transaction_id = _normalize_tx_id(pg_transaction_id)
    if await _payment_already_recorded(db, platform, pg_transaction_id, status):
        logger.info(
            "Webhook: 이미 기록된 결제 건너뜀 platform=%s tx=%s status=%s",
            platform, pg_transaction_id, status,
        )
        return False

    history = PaymentHistory(
        user_id=user_id,
        subscription_id=subscription_id,
        amount=amount,
        status=status,
        platform=platform,
        pg_transaction_id=pg_transaction_id,
        pg_response=pg_response,
    )
    # paid_at 없으면 모델 default(now())가 적용되도록 명시 설정을 건너뛴다.
    if paid_at is not None:
        history.created_at = paid_at
    try:
        async with db.begin_nested():
            db.add(history)
    except IntegrityError:
        logger.info(
            "Webhook: 동시 적재 경합 감지, 건너뜀 platform=%s tx=%s status=%s",
            platform, pg_transaction_id, status,
        )
        return False
    return True


async def _cancel_existing_active(user_id, db: AsyncSession) -> None:
    """기존 활성 구독 취소."""
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
    )
    for old_sub in existing.scalars().all():
        old_sub.status = "cancelled"
        old_sub.cancelled_at = datetime.now(timezone.utc)


async def activate_store_subscription(
    user_id,
    platform: str,
    product_id: str,
    transaction_id: str,
    original_transaction_id: str | None,
    expires_at: datetime | None,
    auto_renewing: bool,
    raw_response: dict,
    db: AsyncSession,
) -> Subscription:
    """스토어 IAP 구독 활성화 (Google/Apple 공통)."""
    # 상품 → 플랜 매핑
    if platform == "android":
        plan = google_product_to_plan(product_id)
    elif platform == "ios":
        plan = apple_product_to_plan(product_id)
    else:
        raise ValueError(f"Unknown platform: {platform}")

    if not plan:
        raise ValueError(f"Unknown product_id: {product_id}")

    # 금액 매핑 누락 가드: GOOGLE_PRODUCTS/APPLE_PRODUCTS엔 plan이 있는데
    # PLAN_AMOUNTS엔 빠져 있으면(미래 상품 추가·금액 누락) .get(plan, 0)이
    # 0원 success를 박아서 매출이 조용히 누락된다. None이면 막고 큰 소리로 터뜨린다.
    amount = PLAN_AMOUNTS.get(plan)
    if amount is None:
        raise ValueError(
            f"PLAN_AMOUNTS에 금액 매핑 없음: plan={plan!r} "
            f"(platform={platform}, product_id={product_id}) — store_products.PLAN_AMOUNTS에 추가 필요"
        )
    now = datetime.now(timezone.utc)

    # 동일 original_transaction_id로 기존 구독 조회 (갱신인 경우)
    lookup_key = original_transaction_id or transaction_id
    existing_result = await db.execute(
        select(Subscription).where(
            Subscription.store_original_transaction_id == lookup_key,
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    existing_sub = existing_result.scalar_one_or_none()

    if existing_sub:
        # 기존 구독 갱신 (플랜 변경 포함)
        existing_sub.status = "active"
        existing_sub.plan = plan
        existing_sub.store_product_id = product_id
        existing_sub.store_transaction_id = transaction_id
        existing_sub.expires_at = expires_at
        existing_sub.auto_renewing = auto_renewing
        existing_sub.updated_at = now
        existing_sub.next_billing_at = expires_at
        existing_sub.amount = amount
        sub = existing_sub
    else:
        # 기존 활성 구독 취소
        await _cancel_existing_active(user_id, db)

        # 새 구독 생성
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            platform=platform,
            store_product_id=product_id,
            store_transaction_id=transaction_id,
            store_original_transaction_id=lookup_key,
            auto_renewing=auto_renewing,
            amount=amount,
            started_at=now,
            expires_at=expires_at,
            next_billing_at=expires_at,
        )
        db.add(sub)
        # 결제 기록 전에 flush해서 sub.id를 채운다.
        # id는 파이썬 default(uuid4)라 flush 전엔 None이라서, 안 하면 결제 행의
        # subscription_id가 NULL로 들어가 구독이랑 안 엮인다(환불 회수·매출 추적에 필요).
        await db.flush()

    # 결제 기록 (verify 재시도/웹훅 경합에도 멱등 — 같은 거래 중복이면 조용히 건너뜀)
    await _record_payment_idempotent(
        db,
        user_id=user_id,
        subscription_id=sub.id,
        amount=amount,
        status="success",
        platform=platform,
        pg_transaction_id=transaction_id,
        pg_response=raw_response,
    )

    # User.plan 업데이트
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.plan = plan
        await sync_area_activation(user_id, plan, db)

    # 퍼널 계측: 유료전환 (최초 1회)
    from backend.app.services.funnel import log_funnel_event, EV_PAID
    await log_funnel_event(db, EV_PAID, user_id, props={"plan": plan, "platform": platform}, once=True)

    await db.flush()
    return sub


async def handle_store_event(
    platform: str,
    event_type: str,
    original_transaction_id: str,
    transaction_id: str | None,
    product_id: str | None,
    expires_at: datetime | None,
    auto_renewing: bool,
    raw_payload: dict,
    db: AsyncSession,
) -> dict:
    """스토어 웹훅 이벤트 처리 (갱신, 취소, 만료 등)."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.store_original_transaction_id == original_transaction_id,
        ).order_by(Subscription.created_at.desc()).limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("Webhook: 구독 없음 original_tx=%s", original_transaction_id)
        return {"status": "subscription_not_found"}

    now = datetime.now(timezone.utc)
    # 실제 결제(이벤트) 시각 — 결제 기록 created_at에 쓴다. 못 뽑으면 None → now() 폴백.
    paid_at = _store_event_paid_at(platform, raw_payload, event_type)

    # 이벤트 타입별 처리
    if event_type in ("RENEWED", "DID_RENEW", "SUBSCRIBED", "SUBSCRIPTION_STATE_ACTIVE"):
        sub.status = "active"
        if expires_at:
            sub.expires_at = expires_at
            sub.next_billing_at = expires_at
        if transaction_id:
            sub.store_transaction_id = transaction_id
        sub.auto_renewing = auto_renewing
        sub.updated_at = now

        # 결제 기록 (재전송/경합에도 멱등 — 중복이면 조용히 건너뜀)
        await _record_payment_idempotent(
            db,
            user_id=sub.user_id,
            subscription_id=sub.id,
            amount=sub.amount,
            status="success",
            platform=platform,
            pg_transaction_id=transaction_id or original_transaction_id,
            pg_response=raw_payload,
            paid_at=paid_at,
        )

        # User.plan 갱신
        user_result = await db.execute(select(User).where(User.id == sub.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = sub.plan
            await sync_area_activation(sub.user_id, sub.plan, db)

        # 퍼널 계측: 유료전환 (최초 1회 — 갱신은 중복 적재 안 됨)
        from backend.app.services.funnel import log_funnel_event, EV_PAID
        await log_funnel_event(db, EV_PAID, sub.user_id, props={"plan": sub.plan, "platform": platform}, once=True)

    elif event_type in ("CANCELED", "EXPIRED", "DID_FAIL_TO_RENEW", "REVOKE",
                         "SUBSCRIPTION_STATE_EXPIRED", "SUBSCRIPTION_STATE_REVOKED"):
        sub.status = "expired"
        sub.auto_renewing = False
        sub.cancelled_at = now
        sub.updated_at = now

        # User.plan → free (다른 활성 구독이 없으면)
        other_active = await db.execute(
            select(Subscription).where(
                Subscription.user_id == sub.user_id,
                Subscription.id != sub.id,
                Subscription.status.in_(["active", "trial"]),
            ).limit(1)
        )
        if not other_active.scalar_one_or_none():
            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = "free"
                await sync_area_activation(sub.user_id, "free", db)

    elif event_type in ("IN_GRACE_PERIOD", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
        sub.status = "grace_period"
        sub.auto_renewing = auto_renewing
        sub.updated_at = now

    elif event_type in ("ON_HOLD", "SUBSCRIPTION_STATE_ON_HOLD"):
        sub.status = "billing_retry"
        sub.auto_renewing = False
        sub.updated_at = now

    elif event_type in ("REFUND", "REVOKED"):
        # REFUND: 애플 환불 알림. REVOKED: 구글 RTDN 타입 12(환불·차지백으로 만료 전 구독 회수).
        # 예전엔 "REVOKED"가 취소 그룹("REVOKE"/"SUBSCRIPTION_STATE_REVOKED")과 철자가 달라
        # 어디에도 안 걸리고 통째로 무시됐다 → 구독이 안 끊기고(유저는 pro 유지) 원결제도
        # 매출에 그대로 남았다. 환불로 똑같이 처리한다(매출 차감 + 등급 회수).
        sub.status = "expired"
        sub.auto_renewing = False
        sub.updated_at = now

        # 환불은 원래 success 결제행을 refunded로 '뒤집어서' 매출(success 합산)에서 빠지게 한다.
        # 예전엔 별도 refunded 행만 추가하고 success 행을 그대로 둬서, 환불해도 매출이
        # 안 줄어드는 버그가 있었다(dodo 환불은 원행을 뒤집는데 스토어만 안 했음).
        # 뒤집을 원행 매칭: 같은 거래번호의 success 행 우선 → 없으면 이 구독의 최신 success 행.
        refund_tx = _normalize_tx_id(transaction_id or original_transaction_id)
        paid = None
        if refund_tx:
            res = await db.execute(
                select(PaymentHistory).where(
                    PaymentHistory.platform == platform,
                    PaymentHistory.pg_transaction_id == refund_tx,
                    PaymentHistory.status == "success",
                ).limit(1)
            )
            paid = res.scalar_one_or_none()
        if paid is None:
            res = await db.execute(
                select(PaymentHistory).where(
                    PaymentHistory.subscription_id == sub.id,
                    PaymentHistory.status == "success",
                ).order_by(PaymentHistory.created_at.desc()).limit(1)
            )
            paid = res.scalar_one_or_none()

        if paid is not None:
            # success → refunded 로 상태 전환(행 추가 아님). savepoint로 감싸서, 같은 거래의
            # refunded 행이 이미 있던 비정상 데이터면 유니크 인덱스(platform, tx, status)에
            # 걸려도 500 안 내고 중복 success 행을 제거한다(dodo 환불과 동일 처리).
            try:
                async with db.begin_nested():
                    paid.status = "refunded"
                    await db.flush()
            except IntegrityError:
                logger.info(
                    "Webhook 환불: refunded 행 이미 존재 → 중복 success 행 제거 tx=%s",
                    paid.pg_transaction_id,
                )
                await db.delete(paid)
                await db.flush()
        else:
            # 뒤집을 success 행이 없음 — 이미 환불 처리됐거나(재전송) 원결제 기록 자체가 없던 경우.
            # 이미 이 구독에 refunded 행이 있으면 멱등 스킵, 없으면 환불 사실만 기록(매출 영향 없음).
            existing_refunded = await db.execute(
                select(PaymentHistory.id).where(
                    PaymentHistory.subscription_id == sub.id,
                    PaymentHistory.status == "refunded",
                ).limit(1)
            )
            if existing_refunded.scalar_one_or_none() is None:
                await _record_payment_idempotent(
                    db,
                    user_id=sub.user_id,
                    subscription_id=sub.id,
                    amount=sub.amount,
                    status="refunded",
                    platform=platform,
                    pg_transaction_id=refund_tx,
                    pg_response=raw_payload,
                    paid_at=paid_at,
                )
            else:
                logger.info("Webhook 환불: 이미 환불 처리됨, 건너뜀 sub=%s", sub.id)

        # User.plan → free
        user_result = await db.execute(select(User).where(User.id == sub.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = "free"
            await sync_area_activation(sub.user_id, "free", db)
    else:
        logger.info("Webhook: 미처리 이벤트 type=%s", event_type)
        return {"status": "ignored", "event_type": event_type}

    await db.flush()
    return {"status": "ok", "event_type": event_type, "subscription_id": str(sub.id)}
