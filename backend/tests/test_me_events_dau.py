"""/me/events 인증요청이 DAU에 잡히는지 검증 — 프론트 부트스트랩(app_open) 핑이 의존하는 계약.

배경:
재방문 로그인 유저가 앱만 열고 아무 인증 API도 안 부르는 화면에 머물면 daily_active가
안 박혀서 오늘 DAU에서 통째로 빠진다(언더카운트). 프론트는 앱 로드마다 토큰이 있으면
/me/events(app_open)를 1회 보내서 이걸 막는다(frontend/app/providers.tsx의 DailyActiveBootstrap).

이 요청이 백엔드에서 거치는 경로:
  POST /me/events → get_optional_user → get_current_user(여기서 daily_active 적재) → track_event

검증 포인트:
1. 토큰 달고 /me/events(app_open)를 보내면 '오늘 첫 인증요청'이라 daily_active가 적재되고
   admin DAU에 잡힌다 (= 재방문 유저 언더카운트 해소).
2. app_open은 CORE_ACTION_EVENTS가 아니라서 활성화(activation) 지표는 오염시키지 않는다.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func, delete

import backend.app.core.auth as auth_module
from backend.app.core.auth import get_optional_user, KST
from backend.app.models.app_event import AppEvent
from backend.app.routers.me import track_event, EventBody
from backend.app.routers.admin import _dau_query
from backend.app.services.funnel import (
    EV_DAILY_ACTIVE, EV_ACTIVATION, CORE_ACTION_EVENTS, compute_funnel_metrics,
)

UTC = timezone.utc


def _today_start_kst() -> datetime:
    return datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)


async def _post_app_open(db, x_dev_uid: str):
    """프론트 부트스트랩 핑을 그대로 재현: /me/events 경로의 의존성(get_optional_user)을
    먼저 풀고(여기서 daily_active 적재), 이어서 track_event 핸들러를 호출."""
    user = await get_optional_user(authorization=None, x_dev_uid=x_dev_uid, db=db)
    await track_event(
        body=EventBody(name="app_open", props={"source": "bootstrap"},
                       session_id="boot", platform="web"),
        current_user=user, db=db,
    )
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_app_open_counts_returning_user_in_dau(db, monkeypatch):
    """재방문 유저가 app_open 핑만 보내도 오늘 DAU에 잡힌다."""
    monkeypatch.setattr(auth_module, "DISABLE_AUTH", True)
    today_start = _today_start_kst()
    x_uid = f"dev-{uuid.uuid4()}"

    # 1) 가입(첫 인증). 그 뒤 '어제 마지막 활동' 상태로 되돌려 오늘 DAU에서 빠진 상황 재현.
    user = await get_optional_user(authorization=None, x_dev_uid=x_uid, db=db)
    await db.flush()
    await db.execute(delete(AppEvent).where(
        AppEvent.user_id == user.id, AppEvent.name == EV_DAILY_ACTIVE,
    ))
    user.last_active = datetime.now(UTC) - timedelta(days=1)
    await db.flush()
    assert (await db.execute(_dau_query(today_start))).scalar() == 0  # 오늘 활동 없음

    # 2) 앱 로드 → 부트스트랩 app_open 핑 1회 → daily_active 적재 → 오늘 DAU=1
    await _post_app_open(db, x_uid)
    assert (await db.execute(_dau_query(today_start))).scalar() == 1


@pytest.mark.asyncio
async def test_app_open_does_not_pollute_activation(db, monkeypatch):
    """app_open은 핵심행동이 아니므로 activation 이벤트/지표를 만들지 않는다."""
    monkeypatch.setattr(auth_module, "DISABLE_AUTH", True)
    assert "app_open" not in CORE_ACTION_EVENTS

    user = await _post_app_open(db, f"dev-{uuid.uuid4()}")

    activation_events = (await db.execute(
        select(func.count()).select_from(AppEvent).where(
            AppEvent.user_id == user.id,
            AppEvent.name.in_(tuple(CORE_ACTION_EVENTS) + (EV_ACTIVATION,)),
        )
    )).scalar()
    assert activation_events == 0

    metrics = await compute_funnel_metrics(db, datetime.now(UTC))
    assert metrics["funnel"]["activation"] == 0
