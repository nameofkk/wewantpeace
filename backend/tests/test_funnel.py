"""퍼널 계측 테스트 — 이벤트 적재(once/once_per_day) + 지표 집계."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from backend.app.models.user import User
from backend.app.models.app_event import AppEvent
from backend.app.models.subscription import PaymentHistory
from backend.app.services.funnel import (
    log_funnel_event, compute_funnel_metrics,
    EV_SIGNUP, EV_ACTIVATION, EV_PAID,
)

UTC = timezone.utc


def _user(created: datetime, status="active") -> User:
    return User(
        id=uuid.uuid4(),
        firebase_uid=f"fb-{uuid.uuid4()}",
        plan="free",
        status=status,
        created_at=created,
        last_active=created,
    )


def _ev(uid, name, when, session_id=None):
    return AppEvent(user_id=uid, name=name, created_at=when, session_id=session_id, platform="web")


@pytest.mark.asyncio
async def test_log_funnel_event_once(db):
    u = _user(datetime(2026, 6, 1, tzinfo=UTC))
    db.add(u)
    await db.flush()

    first = await log_funnel_event(db, EV_ACTIVATION, u.id, once=True)
    second = await log_funnel_event(db, EV_ACTIVATION, u.id, once=True)
    assert first is True
    assert second is False

    from sqlalchemy import select, func
    cnt = (await db.execute(
        select(func.count()).select_from(AppEvent).where(
            AppEvent.user_id == u.id, AppEvent.name == EV_ACTIVATION)
    )).scalar()
    assert cnt == 1


@pytest.mark.asyncio
async def test_log_funnel_event_once_per_day(db):
    u = _user(datetime(2026, 6, 1, tzinfo=UTC))
    db.add(u)
    await db.flush()

    a = await log_funnel_event(db, "return", u.id, once_per_day=True)
    b = await log_funnel_event(db, "return", u.id, once_per_day=True)
    assert a is True
    assert b is False


@pytest.mark.asyncio
async def test_compute_funnel_metrics(db):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)

    # A: 40일 전 가입, 가입 다음날 재방문 + 핵심행동 → 활성화/재방문/D1 리텐션
    a = _user(datetime(2026, 5, 1, tzinfo=UTC))
    # B: 40일 전 가입, 활동 없음 (backfill row만 → 제외돼야 함)
    b = _user(datetime(2026, 5, 1, tzinfo=UTC))
    # C: 1일 전 가입, 핵심행동 + 오늘 재방문 + 유료결제 → 활성화/재방문/전환/D1
    c = _user(datetime(2026, 6, 9, tzinfo=UTC))
    # D: 오늘 가입, 활동 없음 → 어느 리텐션 코호트에도 안 들어감
    d = _user(datetime(2026, 6, 10, 8, 0, tzinfo=UTC))
    for u in (a, b, c, d):
        db.add(u)
    await db.flush()

    db.add_all([
        _ev(a.id, "issue_view", datetime(2026, 5, 1, 9, tzinfo=UTC)),       # 활성화
        _ev(a.id, "dashboard_view", datetime(2026, 5, 2, 9, tzinfo=UTC)),   # D1 재방문
        _ev(b.id, "issue_view", datetime(2026, 5, 2, 9, tzinfo=UTC), session_id="backfill"),  # 제외
        _ev(c.id, "watch_country_add", datetime(2026, 6, 9, 9, tzinfo=UTC)),  # 활성화
        _ev(c.id, "issue_view", datetime(2026, 6, 10, 9, tzinfo=UTC)),        # D1 재방문
    ])
    db.add(PaymentHistory(user_id=c.id, amount=699, status="success", platform="dodopayments"))
    await db.flush()

    m = await compute_funnel_metrics(db, now)

    assert m["funnel"]["signup"] == 4
    assert m["funnel"]["activation"] == 2      # A, C
    assert m["funnel"]["return"] == 2          # A, C
    assert m["funnel"]["paid"] == 1            # C

    assert m["activation_rate"] == 50.0        # 2/4
    assert m["conversion_rate"] == 25.0        # 1/4

    # D1 코호트: A,B,C (D는 아직 1일 안 지남) / retained: A,C
    assert m["retention_detail"]["d1"]["cohort_size"] == 3
    assert m["retention_detail"]["d1"]["retained"] == 2
    assert m["retention_d1"] == 66.7

    # D7 코호트: A,B (C는 7일 안 지남) / retained: 0
    assert m["retention_detail"]["d7"]["cohort_size"] == 2
    assert m["retention_d7"] == 0.0

    # D30 코호트: A,B / retained: 0
    assert m["retention_detail"]["d30"]["cohort_size"] == 2
    assert m["retention_d30"] == 0.0


@pytest.mark.asyncio
async def test_compute_funnel_metrics_empty(db):
    """가입자 0명이어도 0으로 나누지 않고 안전하게 반환."""
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    m = await compute_funnel_metrics(db, now)
    assert m["activation_rate"] == 0.0
    assert m["conversion_rate"] == 0.0
    assert m["funnel"]["signup"] == 0
