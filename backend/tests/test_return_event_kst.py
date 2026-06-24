"""재방문(return) 이벤트 적재의 '오늘' 윈도우는 한국시간(KST) 기준이어야 한다.

배경:
- 지표 계산(compute_funnel_metrics)은 이미 KST(_local_date)로 가입일/활동일을 끊는다.
- 그런데 이벤트 적재(me.track_event)는 예전에 UTC date로 끊어서, 한국 새벽 0~9시에 가입한
  유저(UTC상 전날 날짜)가 같은 KST 날에 재방문해도 return 이벤트가 잘못 적재됐다.
- 그 결과 적재된 return 이벤트가 지표 기준과 어긋나 '같은 날 재방문'이 return으로 부풀려졌다.

검증:
1. 가입과 재방문이 같은 KST 날(서로 다른 UTC 날)이면 return 이벤트가 적재되면 안 된다.
2. 가입 이후 '다른 KST 날'에 재방문하면 return 이벤트가 적재된다.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func

from backend.app.routers.me import track_event, EventBody
from backend.app.models.user import User
from backend.app.models.app_event import AppEvent
from backend.app.services.funnel import EV_RETURN

UTC = timezone.utc
KST = timezone(timedelta(hours=9))


async def _make_user(db, created_at: datetime) -> User:
    u = User(
        id=uuid.uuid4(), firebase_uid=f"fb-{uuid.uuid4()}",
        plan="free", status="active", created_at=created_at, last_active=created_at,
    )
    db.add(u)
    await db.flush()
    return u


async def _return_count(db, uid) -> int:
    return (await db.execute(
        select(func.count()).select_from(AppEvent).where(
            AppEvent.user_id == uid, AppEvent.name == EV_RETURN,
        )
    )).scalar()


@pytest.mark.asyncio
async def test_no_return_event_same_kst_day(db, monkeypatch):
    """가입과 재방문이 같은 한국 달력일이면(UTC상 가입은 전날) return이 적재되면 안 된다."""
    # 가입: KST 06-10 02:00 = UTC 06-09 17:00 (UTC date는 06-09)
    user = await _make_user(db, datetime(2026, 6, 9, 17, 0, tzinfo=UTC))

    # '지금'을 KST 06-10 11:00 = UTC 06-10 02:00 으로 고정 (같은 KST 날 06-10)
    import backend.app.routers.me as me_mod

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            base = datetime(2026, 6, 10, 2, 0, tzinfo=UTC)
            return base.astimezone(tz) if tz else base

    monkeypatch.setattr(me_mod, "datetime", _FixedDateTime)

    await track_event(EventBody(name="issue_view"), current_user=user, db=db)
    await db.flush()

    # UTC date로 끊었으면 06-09 < 06-10 이라 return이 잘못 적재됨. KST면 둘 다 06-10 → 적재 안 됨.
    assert await _return_count(db, user.id) == 0


@pytest.mark.asyncio
async def test_return_event_next_kst_day(db, monkeypatch):
    """가입 다음 한국 달력일에 재방문하면 return이 적재된다."""
    # 가입: KST 06-09 02:00 = UTC 06-08 17:00
    user = await _make_user(db, datetime(2026, 6, 8, 17, 0, tzinfo=UTC))

    import backend.app.routers.me as me_mod

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            base = datetime(2026, 6, 10, 2, 0, tzinfo=UTC)  # KST 06-10 11:00
            return base.astimezone(tz) if tz else base

    monkeypatch.setattr(me_mod, "datetime", _FixedDateTime)

    await track_event(EventBody(name="issue_view"), current_user=user, db=db)
    await db.flush()

    assert await _return_count(db, user.id) == 1
