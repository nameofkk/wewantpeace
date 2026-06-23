"""DAU 집계 테스트 — last_active(1시간 스로틀) 의존을 떼고 일자별 활동 로그(daily_active)로 셈.

검증 포인트:
1. auth(get_current_user)가 '오늘 첫 인증요청'에 daily_active 이벤트를 하루 1건만 적재한다.
2. admin DAU 쿼리(_dau_query)가 daily_active의 distinct 사용자 수를 센다.
3. 1시간 스로틀의 경계 버그(자정 직후 재방문이 전날 last_active로 남아 DAU에서 새던 문제)가
   daily_active 기반에서는 안 생긴다.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func, delete

import backend.app.core.auth as auth_module
from backend.app.core.auth import get_current_user, KST
from backend.app.models.app_event import AppEvent
from backend.app.models.user import User
from backend.app.routers.admin import _dau_query
from backend.app.services.funnel import EV_DAILY_ACTIVE

UTC = timezone.utc


def _today_start_kst() -> datetime:
    return datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)


async def _make_user(db) -> uuid.UUID:
    """app_events FK(users.id)를 만족시킬 실제 User 한 명 생성하고 id 반환."""
    u = User(id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4()}", plan="free", status="active")
    db.add(u)
    await db.flush()
    return u.id


async def _daily_active_count(db, uid) -> int:
    return (await db.execute(
        select(func.count()).select_from(AppEvent).where(
            AppEvent.user_id == uid, AppEvent.name == EV_DAILY_ACTIVE,
        )
    )).scalar()


@pytest.mark.asyncio
async def test_first_auth_logs_daily_active_once_per_day(db, monkeypatch):
    """오늘 첫 인증요청은 daily_active를 적재하고, 같은 날 재요청은 추가 적재 안 한다."""
    monkeypatch.setattr(auth_module, "DISABLE_AUTH", True)
    uid = f"dev-{uuid.uuid4()}"

    user = await get_current_user(authorization=None, x_dev_uid=uid, db=db)
    await db.flush()
    assert await _daily_active_count(db, user.id) == 1

    # 같은 날 재인증 — last_active 스로틀로 갱신 안 되든 말든, daily_active는 그대로 1건.
    await get_current_user(authorization=None, x_dev_uid=uid, db=db)
    await db.flush()
    assert await _daily_active_count(db, user.id) == 1


@pytest.mark.asyncio
async def test_dau_query_counts_distinct_daily_active_users(db):
    """_dau_query는 오늘 daily_active가 있는 distinct 사용자 수를 센다."""
    today_start = _today_start_kst()
    now = datetime.now(KST)
    yesterday = now - timedelta(days=1)

    u1, u2, u3 = await _make_user(db), await _make_user(db), await _make_user(db)
    # u1: 오늘 1건 / u2: 오늘 2건(중복 들어와도 distinct로 1명) / u3: 어제만 → 오늘 DAU 제외
    db.add_all([
        AppEvent(user_id=u1, name=EV_DAILY_ACTIVE, created_at=now, platform="web"),
        AppEvent(user_id=u2, name=EV_DAILY_ACTIVE, created_at=now, platform="web"),
        AppEvent(user_id=u2, name=EV_DAILY_ACTIVE, created_at=now, platform="web"),
        AppEvent(user_id=u3, name=EV_DAILY_ACTIVE, created_at=yesterday, platform="web"),
    ])
    await db.flush()

    dau = (await db.execute(_dau_query(today_start))).scalar() or 0
    assert dau == 2  # u1, u2 (u3는 어제라 제외)


@pytest.mark.asyncio
async def test_dau_query_ignores_other_event_names(db):
    """daily_active가 아닌 다른 이벤트(signup 등)는 DAU에 안 잡힌다."""
    today_start = _today_start_kst()
    now = datetime.now(KST)
    u = await _make_user(db)
    db.add_all([
        AppEvent(user_id=u, name="signup", created_at=now, platform="web"),
        AppEvent(user_id=u, name="issue_view", created_at=now, platform="web"),
    ])
    await db.flush()

    dau = (await db.execute(_dau_query(today_start))).scalar() or 0
    assert dau == 0


@pytest.mark.asyncio
async def test_midnight_throttle_edge_still_counted(db, monkeypatch):
    """1시간 스로틀 경계 버그 회귀 방지.

    어제 늦게 활동(last_active=어제)한 사용자가 오늘 다시 인증하면, last_active가
    스로틀로 안 바뀌어도 daily_active가 새로 적재돼 오늘 DAU에 잡혀야 한다.
    """
    monkeypatch.setattr(auth_module, "DISABLE_AUTH", True)
    uid = f"dev-{uuid.uuid4()}"
    today_start = _today_start_kst()

    user = await get_current_user(authorization=None, x_dev_uid=uid, db=db)
    await db.flush()

    # '어제 마지막 활동' 상태를 재현: 오늘 적재된 daily_active를 지우고 last_active를 어제로.
    await db.execute(delete(AppEvent).where(
        AppEvent.user_id == user.id, AppEvent.name == EV_DAILY_ACTIVE,
    ))
    user.last_active = datetime.now(UTC) - timedelta(days=1)
    await db.flush()
    assert (await db.execute(_dau_query(today_start))).scalar() == 0  # 아직 오늘 활동 없음

    # 오늘 재인증 → 스로틀과 무관하게 daily_active 적재 → DAU 1
    await get_current_user(authorization=None, x_dev_uid=uid, db=db)
    await db.flush()
    assert (await db.execute(_dau_query(today_start))).scalar() == 1
