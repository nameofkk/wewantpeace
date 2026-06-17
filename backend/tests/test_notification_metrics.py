"""분쟁 알림 가치 전달 계측 테스트 — 전달 건수 + 열람률 집계, 열람 이벤트 적재."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from backend.app.models.user import User
from backend.app.models.app_event import AppEvent
from backend.app.models.notification import Notification
from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.alert_delivery_log import AlertDeliveryLog
from backend.app.services.notification_metrics import (
    compute_notification_metrics,
    log_notif_opened,
    EV_NOTIF_OPENED,
    CONFLICT_NOTIF_TYPES,
)

UTC = timezone.utc


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        firebase_uid=f"fb-{uuid.uuid4()}",
        plan="free",
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_active=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _cluster() -> IssueCluster:
    t = datetime(2026, 6, 1, tzinfo=UTC)
    return IssueCluster(
        id=uuid.uuid4(),
        cluster_key=f"ck-{uuid.uuid4()}",
        geohash5="wydm6",
        topic="conflict",
        title="Test conflict",
        severity=80,
        first_event_at=t, last_event_at=t, window_start=t, window_end=t,
    )


def _push(user_id, cluster_id, decision, when, platform="web", alert_type="verified"):
    return AlertDeliveryLog(
        user_id=user_id, cluster_id=cluster_id, alert_type=alert_type,
        decision=decision, platform=platform, created_at=when,
    )


def _notif(user_id, cluster_id, ntype, when, is_read=False):
    return Notification(
        user_id=user_id, type=ntype, cluster_id=cluster_id,
        title="t", body="b", is_read=is_read, created_at=when,
    )


@pytest.mark.asyncio
async def test_log_notif_opened_writes_event(db):
    u = _user()
    db.add(u)
    await db.flush()

    ok = await log_notif_opened(db, u.id, channel="push", cluster_id=str(uuid.uuid4()))
    await db.flush()
    assert ok is True

    from sqlalchemy import select, func
    cnt = (await db.execute(
        select(func.count()).select_from(AppEvent).where(
            AppEvent.user_id == u.id, AppEvent.name == EV_NOTIF_OPENED)
    )).scalar()
    assert cnt == 1


@pytest.mark.asyncio
async def test_compute_notification_metrics(db):
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    recent = now - timedelta(days=2)    # d7/d30/total 전부 포함
    old = now - timedelta(days=20)      # d30/total (d7 제외)
    ancient = now - timedelta(days=40)  # total만 (d7/d30 제외)

    u1, u2 = _user(), _user()
    c = _cluster()
    for x in (u1, u2, c):
        db.add(x)
    await db.flush()

    # ── 푸시 전달(alert_delivery_log) ──
    # u1: 같은 클러스터를 2기기로 sent(recent) → sent 행 2개지만 도달 사용자는 1명
    # u2: sent(old) 1건
    # 그리고 pending/failed/suppressed는 '전달'에 안 들어가야 함
    db.add_all([
        _push(u1.id, c.id, "sent", recent, platform="web"),
        _push(u1.id, c.id, "sent", recent, platform="android"),
        _push(u2.id, c.id, "sent", old),
        _push(u2.id, c.id, "pending", recent),
        _push(u2.id, c.id, "failed", recent),
        _push(u1.id, c.id, "suppressed", recent),
    ])

    # ── 인앱 전달(notifications) ──
    # 분쟁 타입(verified/fast/spike) 5건 + 마케팅(trial_nudge) 1건(제외 대상)
    # recent 중 verified read=True 1건, fast read=False 1건 → d7 열람률 50%
    db.add_all([
        _notif(u1.id, c.id, "verified", recent, is_read=True),
        _notif(u1.id, c.id, "fast", recent, is_read=False),
        _notif(u2.id, c.id, "spike", old, is_read=True),
        _notif(u2.id, c.id, "verified", ancient, is_read=False),
        _notif(u1.id, c.id, "fast", ancient, is_read=True),
        _notif(u1.id, None, "trial_nudge", recent, is_read=True),  # 분쟁 알림 아님 → 제외
    ])

    # ── 열람 이벤트(going-forward) ──
    db.add_all([
        AppEvent(user_id=u1.id, name=EV_NOTIF_OPENED, created_at=recent, platform="web"),
        AppEvent(user_id=u2.id, name=EV_NOTIF_OPENED, created_at=old, platform="web"),  # d7 밖
    ])
    await db.flush()

    m = (await compute_notification_metrics(db, now))["notifications"]

    assert list(CONFLICT_NOTIF_TYPES) == m["conflict_types"]

    # 푸시 전달(sent 행 수): 전체 3, d30 3, d7 2 (old 1건은 d7 밖)
    assert m["push_delivered"] == {"total": 3, "d7": 2, "d30": 3}
    # 도달 사용자(user,cluster distinct): 전체 2(u1,u2), d7 1(u1만), d30 2
    assert m["push_users_reached"] == {"total": 2, "d7": 1, "d30": 2}

    # 인앱 전달(분쟁 타입만, trial_nudge 제외): 전체 5, d30 3(recent2+old1), d7 2
    assert m["inapp_delivered"] == {"total": 5, "d7": 2, "d30": 3}
    # 인앱 열람(is_read): 전체 3(verified recent, spike old, fast ancient), d30 2, d7 1
    assert m["inapp_read"] == {"total": 3, "d7": 1, "d30": 2}
    # 열람률 = 읽음/전달: total 3/5=60.0, d7 1/2=50.0, d30 2/3=66.7
    assert m["inapp_read_rate"] == {"total": 60.0, "d7": 50.0, "d30": 66.7}

    # 열람 이벤트 d7: recent 1건만
    assert m["opened_events_d7"] == 1


@pytest.mark.asyncio
async def test_compute_notification_metrics_empty(db):
    """데이터 0건이어도 0으로 나누지 않고 안전하게 반환."""
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    m = (await compute_notification_metrics(db, now))["notifications"]
    assert m["push_delivered"]["total"] == 0
    assert m["inapp_delivered"]["total"] == 0
    assert m["inapp_read_rate"]["total"] == 0.0
    assert m["opened_events_d7"] == 0
