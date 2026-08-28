"""탈퇴(soft delete, status='deleted') 유저가 '오늘' 윈도우 집계와 퍼널 분자에서 빠지는지 검증.

배경: 탈퇴는 행을 지우지 않고 status만 'deleted'로 바꾸는 soft delete라, app_events/
payment_history의 user_id가 그대로 남는다(FK ondelete=SET NULL은 행이 진짜 DELETE될 때만
걸림). 그래서 total_users·funnel.signup(분모)은 탈퇴를 빼는데, new_today·DAU·activation·
paid(분자)가 안 빼면 지표가 부풀려지고 비율이 100%를 넘기도 한다.

검증:
1. _dau_query는 탈퇴 유저의 daily_active를 안 센다.
2. new_today 윈도우(created_at>=today, status!=deleted)가 탈퇴 가입자를 안 센다.
3. funnel activation/paid가 탈퇴 유저를 분자에서 뺀다 → activation_rate가 100% 안 넘는다.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func

from backend.app.core.auth import KST
from backend.app.models.app_event import AppEvent
from backend.app.models.user import User
from backend.app.models.subscription import PaymentHistory
from backend.app.routers.admin import _dau_query, _today_start_kst
from backend.app.services.funnel import EV_DAILY_ACTIVE, compute_funnel_metrics

UTC = timezone.utc




async def _make_user(db, status="active", created_at=None) -> uuid.UUID:
    u = User(
        id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4()}", plan="free", status=status,
    )
    if created_at is not None:
        u.created_at = created_at
    db.add(u)
    await db.flush()
    return u.id


@pytest.mark.asyncio
async def test_dau_excludes_soft_deleted_user(db):
    """탈퇴 유저가 오늘 daily_active를 남겼어도 DAU에 안 잡힌다."""
    today_start = _today_start_kst()
    now = datetime.now(KST).astimezone(UTC)  # SQLite 문자열 비교 안전을 위해 UTC로 정규화

    active_uid = await _make_user(db, status="active")
    deleted_uid = await _make_user(db, status="deleted")
    db.add_all([
        AppEvent(user_id=active_uid, name=EV_DAILY_ACTIVE, created_at=now, platform="web"),
        AppEvent(user_id=deleted_uid, name=EV_DAILY_ACTIVE, created_at=now, platform="web"),
    ])
    await db.flush()

    dau = (await db.execute(_dau_query(today_start))).scalar() or 0
    assert dau == 1  # active만, 탈퇴 유저는 제외


@pytest.mark.asyncio
async def test_new_today_excludes_soft_deleted(db):
    """오늘 가입했다가 탈퇴한 유저는 new_today 윈도우에서 빠진다."""
    today_start = _today_start_kst()
    now = datetime.now(UTC)

    await _make_user(db, status="active", created_at=now)
    await _make_user(db, status="deleted", created_at=now)

    new_today = (await db.execute(
        select(func.count()).select_from(User).where(
            User.created_at >= today_start, User.status != "deleted",
        )
    )).scalar() or 0
    assert new_today == 1


@pytest.mark.asyncio
async def test_funnel_activation_paid_exclude_soft_deleted(db):
    """탈퇴 유저는 activation/paid 분자에서 빠져 비율이 분모를 안 넘는다.

    가입자(분모) = active 1명. 탈퇴 유저가 핵심행동·결제를 했어도 분자에 들어가면
    activation_rate가 200% 같은 말도 안 되는 값이 된다.
    """
    now = datetime.now(UTC)
    active_uid = await _make_user(db, status="active", created_at=now)
    deleted_uid = await _make_user(db, status="deleted", created_at=now)

    # 두 유저 모두 핵심행동(issue_view) + 성공 결제를 했다고 가정
    db.add_all([
        AppEvent(user_id=active_uid, name="issue_view", created_at=now, platform="web"),
        AppEvent(user_id=deleted_uid, name="issue_view", created_at=now, platform="web"),
        PaymentHistory(
            user_id=active_uid, amount=699, currency="USD", status="success",
            platform="dodopayments", created_at=now,
        ),
        PaymentHistory(
            user_id=deleted_uid, amount=699, currency="USD", status="success",
            platform="dodopayments", created_at=now,
        ),
    ])
    await db.flush()

    m = await compute_funnel_metrics(db, now)
    assert m["funnel"]["signup"] == 1       # 분모: active만
    assert m["funnel"]["activation"] == 1   # 분자: active만 (탈퇴 제외)
    assert m["funnel"]["paid"] == 1         # 분자: active만 (탈퇴 제외)
    assert m["activation_rate"] == 100.0    # 200%가 아니라 100%
    assert m["conversion_rate"] == 100.0
