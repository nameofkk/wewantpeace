"""분쟁 알림 '가치 전달' 계측 — 실제 전달된 알림 건수 + 열람률(노스스타).

목적(왜 이게 노스스타냐):
- 우리 서비스가 사용자에게 주는 핵심 가치는 '분쟁 알림을 제때 전달'하는 것.
- 그래서 502 같은 장애에서 복구된 뒤 "가치가 실제로 다시 전달되고 있나"를 보려면
  알림을 몇 건이나 실제로 보냈고(전달), 사용자가 몇 건이나 열어봤는지(열람률)를 봐야 한다.

설계(funnel.py와 같은 철학):
- 지표는 원천 테이블에서 직접 집계한다 → 이벤트 적재를 일부 놓쳐도 숫자는 견고하고,
  과거 데이터에도 소급 적용된다.
  · 푸시 전달  = alert_delivery_log.decision='sent' (FCM ACK 받은 실제 도달 건)
  · 인앱 전달  = notifications 중 분쟁 알림 타입(verified/fast/spike) 행
  · 인앱 열람  = 위 중 is_read=True
- 푸시 '열람(탭해서 들어옴)'은 원천 테이블에 없다 → app_events의 notif_opened 이벤트로
  지금부터 적재해서 본다(과거 소급 불가, 지금부터라도). 인앱 읽음도 같은 이벤트를 같이 남긴다.

메일은? 분쟁 알림은 푸시 + 인앱으로만 나간다(메일은 주간 리포트/구독 안내용이라 '분쟁 알림'
단위로 세는 채널이 아님). 그래서 전달 채널은 push/inapp 두 개로 집계한다. 나중에 분쟁 알림을
메일로도 쏘게 되면 notif_opened의 channel='email'과 별도 원천 카운트만 더하면 된다.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.app_event import AppEvent
from backend.app.services.funnel import log_funnel_event

logger = logging.getLogger(__name__)

# 분쟁 알림(인앱)으로 치는 type. 구독 라이프사이클/마케팅 알림(trial_nudge, expired_offer 등)은
# '분쟁 알림'이 아니라 가치 전달 지표에서 뺀다.
CONFLICT_NOTIF_TYPES = ("verified", "fast", "spike")

# 사용자가 알림을 '열어봤다'는 이벤트 이름.
EV_NOTIF_OPENED = "notif_opened"

# 프론트가 푸시/인앱을 탭했을 때 /me/events로 보내는 이벤트 이름들 → notif_opened로 수렴시킨다.
NOTIF_OPEN_EVENT_NAMES = {
    "notification_open", "notification_click", "push_open", "notif_open",
}


async def log_notif_opened(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    *,
    channel: str = "inapp",
    notif_id: int | None = None,
    cluster_id: str | None = None,
    session_id: str | None = None,
    platform: str = "web",
) -> bool:
    """알림 열람 이벤트 한 건 적재(app_events). 계측 실패가 본 기능을 깨지 않도록 방어적.

    channel: 'inapp'(앱 안 알림함에서 읽음) | 'push'(푸시 탭) | 'email'.
    """
    props: dict = {"channel": channel}
    if notif_id is not None:
        props["notif_id"] = notif_id
    if cluster_id:
        props["cluster_id"] = str(cluster_id)
    return await log_funnel_event(
        db, EV_NOTIF_OPENED, user_id,
        props=props, session_id=session_id, platform=platform,
    )


async def _count(db: AsyncSession, q) -> int:
    return int((await db.execute(q)).scalar() or 0)


async def compute_notification_metrics(db: AsyncSession, now: datetime) -> dict:
    """분쟁 알림 전달 건수 + 열람률 집계.

    원천 테이블(alert_delivery_log, notifications)에서 직접 세므로 과거에도 소급 적용된다.
    창(window): 전체(total) / 최근 7일(d7) / 최근 30일(d30).
    """
    from backend.app.models.notification import Notification
    from backend.app.models.alert_delivery_log import AlertDeliveryLog

    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    # ── 푸시 전달: alert_delivery_log decision='sent' (FCM ACK 받은 실제 도달) ──
    def _push_sent(since: datetime | None):
        q = select(func.count()).select_from(AlertDeliveryLog).where(
            AlertDeliveryLog.decision == "sent"
        )
        if since is not None:
            q = q.where(AlertDeliveryLog.created_at >= since)
        return q

    # 같은 알림을 여러 기기로 받으면 sent 행이 여러 개 → '도달한 사용자 수'는 (user,cluster) distinct로.
    def _push_users(since: datetime | None):
        inner = select(AlertDeliveryLog.user_id, AlertDeliveryLog.cluster_id).where(
            AlertDeliveryLog.decision == "sent"
        )
        if since is not None:
            inner = inner.where(AlertDeliveryLog.created_at >= since)
        return select(func.count()).select_from(inner.distinct().subquery())

    # ── 인앱 전달 / 열람: notifications 중 분쟁 알림 타입 ──
    def _inapp(since: datetime | None, read_only: bool):
        q = select(func.count()).select_from(Notification).where(
            Notification.type.in_(CONFLICT_NOTIF_TYPES)
        )
        if read_only:
            q = q.where(Notification.is_read == True)  # noqa: E712
        if since is not None:
            q = q.where(Notification.created_at >= since)
        return q

    push_sent_total = await _count(db, _push_sent(None))
    push_sent_7d = await _count(db, _push_sent(d7))
    push_sent_30d = await _count(db, _push_sent(d30))

    push_users_total = await _count(db, _push_users(None))
    push_users_7d = await _count(db, _push_users(d7))
    push_users_30d = await _count(db, _push_users(d30))

    inapp_total = await _count(db, _inapp(None, False))
    inapp_7d = await _count(db, _inapp(d7, False))
    inapp_30d = await _count(db, _inapp(d30, False))

    inapp_read_total = await _count(db, _inapp(None, True))
    inapp_read_7d = await _count(db, _inapp(d7, True))
    inapp_read_30d = await _count(db, _inapp(d30, True))

    def _rate(read: int, delivered: int) -> float:
        return round(read / delivered * 100, 1) if delivered else 0.0

    # 열람 이벤트(지금부터 적재되는 going-forward 신호 — 푸시 탭 포함)
    opened_events_7d = await _count(
        db,
        select(func.count()).select_from(AppEvent).where(
            AppEvent.name == EV_NOTIF_OPENED,
            AppEvent.created_at >= d7,
        ),
    )

    return {
        "notifications": {
            "conflict_types": list(CONFLICT_NOTIF_TYPES),
            # 실제 전달된 분쟁 알림 건수
            "push_delivered": {"total": push_sent_total, "d7": push_sent_7d, "d30": push_sent_30d},
            "push_users_reached": {"total": push_users_total, "d7": push_users_7d, "d30": push_users_30d},
            "inapp_delivered": {"total": inapp_total, "d7": inapp_7d, "d30": inapp_30d},
            # 열람(인앱 읽음) + 열람률(%)
            "inapp_read": {"total": inapp_read_total, "d7": inapp_read_7d, "d30": inapp_read_30d},
            "inapp_read_rate": {
                "total": _rate(inapp_read_total, inapp_total),
                "d7": _rate(inapp_read_7d, inapp_7d),
                "d30": _rate(inapp_read_30d, inapp_30d),
            },
            # 열람 이벤트 카운트(푸시 탭 포함, 지금부터 누적)
            "opened_events_d7": opened_events_7d,
        }
    }
