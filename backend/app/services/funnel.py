"""퍼널 계측 — 가입/활성화(첫 핵심행동)/재방문/유료전환 이벤트 적재 + 지표 계산.

핵심 퍼널: signup → activation → return → paid

- 이벤트는 app_events 테이블에 적재된다 (user_id + created_at 필수).
- 지표(activation_rate, retention, conversion_rate)는 원천 테이블(users, app_events,
  payment_history)에서 직접 집계한다. 따라서 이벤트 적재를 일부 놓쳐도 지표는 견고하다.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta, date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.app_event import AppEvent

logger = logging.getLogger(__name__)

# 표준 퍼널 이벤트 이름
EV_SIGNUP = "signup"
EV_ACTIVATION = "activation"
EV_RETURN = "return"
EV_PAID = "paid"

# 활성화(activation) = 이 서비스의 '가치 첫 경험'.
# WeWantPeace의 핵심 가치는 실제 분쟁 인텔리전스를 직접 들여다보거나(이슈/클러스터 상세),
# 내 관심지역 감시를 설정하는 것. 이 중 하나라도 처음 하면 활성화로 본다.
CORE_ACTION_EVENTS = {"issue_view", "cluster_view", "watch_country_add"}

# 백필/합성 row 제외용 (admin.py 기존 컨벤션과 동일)
_BACKFILL_SESSION = "backfill"

# 리텐션 코호트 조회 lookback 상한 (일). d30까지 커버하려고 넉넉히.
RETENTION_WINDOW_DAYS = 120

# 날짜 경계 기준 타임존. 한국 서비스라 '하루'는 한국시간 자정~자정으로 끊는다.
# (admin.py의 DAU/신규가입/월매출 경계와 동일한 KST 기준 — 대시보드 전체가 같은 '하루'를 봐야 함)
KST = timezone(timedelta(hours=9))


async def log_funnel_event(
    db: AsyncSession,
    name: str,
    user_id: uuid.UUID | None,
    *,
    props: dict | None = None,
    session_id: str | None = None,
    platform: str = "web",
    once: bool = False,
    once_per_day: bool = False,
) -> bool:
    """app_events에 퍼널 이벤트 한 건 적재.

    once=True        : 해당 user_id + name 이벤트가 이미 있으면 적재 안 함 (최초 1회만).
    once_per_day=True: 오늘(KST) 같은 user_id + name 이벤트가 이미 있으면 적재 안 함.

    적재했으면 True, 중복으로 건너뛰면 False.
    flush는 호출부 트랜잭션에 맡긴다(여기선 add만; 단, 중복 체크 쿼리는 즉시 실행).
    """
    try:
        if (once or once_per_day) and user_id is not None:
            q = select(AppEvent.id).where(
                AppEvent.user_id == user_id,
                AppEvent.name == name,
            )
            if once_per_day:
                # 한국시간 자정 기준 '오늘' (timestamptz라 KST aware 값으로 비교하면 DB가 맞춰줌)
                day_start = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
                q = q.where(AppEvent.created_at >= day_start)
            q = q.limit(1)
            existing = (await db.execute(q)).first()
            if existing is not None:
                return False

        db.add(AppEvent(
            user_id=user_id,
            session_id=session_id,
            name=name,
            props=props or None,
            platform=platform,
        ))
        return True
    except Exception:
        # 계측 실패가 본 기능(가입/결제 등)을 깨뜨리면 안 된다.
        logger.exception("log_funnel_event 실패 name=%s user=%s", name, user_id)
        return False


def _local_date(dt: datetime) -> date:
    """timestamp를 KST(한국시간) 기준 날짜로. naive면 UTC로 간주한 뒤 KST로 변환.

    리텐션 코호트/활동일 버킷을 한국 달력 하루로 끊는다. UTC로 끊으면 경계가 한국 오전 9시라
    실제 사용 세션 한복판을 갈라서 가입일·재방문일이 엇갈린다.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).date()


def _retention_from_maps(
    signup_day: dict[uuid.UUID, date],
    activity_days: dict[uuid.UUID, set[date]],
    today: date,
    n: int,
) -> dict:
    """가입일 코호트 기준 Dn 리텐션.

    분모(cohort): 가입 후 n일이 온전히 지난 사용자만 (return할 기회가 있었던 사람).
    분자(retained): 가입일 + n일째에 활동 기록이 있는 사용자.
    """
    cohort = 0
    retained = 0
    for uid, sday in signup_day.items():
        if sday + timedelta(days=n) > today:
            continue  # 아직 n일이 안 지나서 판정 불가 → 코호트에서 제외
        cohort += 1
        if (sday + timedelta(days=n)) in activity_days.get(uid, ()):
            retained += 1
    rate = round(retained / cohort * 100, 1) if cohort else 0.0
    return {"rate": rate, "cohort_size": cohort, "retained": retained}


async def compute_funnel_metrics(db: AsyncSession, now: datetime) -> dict:
    """퍼널 단계별 카운트 + activation_rate / retention_d1·d7·d30 / conversion_rate.

    원천 테이블에서 직접 집계하므로 과거 데이터에도 소급 적용된다.
    리텐션/재방문은 DB 종류(Postgres/SQLite)에 안 타게 윈도 내 활동을 메모리에서 집계한다.
    """
    from backend.app.models.user import User
    from backend.app.models.subscription import PaymentHistory

    # signup = 삭제되지 않은 전체 가입자
    signup = (await db.execute(
        select(func.count()).select_from(User).where(User.status != "deleted")
    )).scalar() or 0

    # activation = 핵심행동(또는 명시적 activation 이벤트)을 한 번이라도 한 distinct 사용자
    activation = (await db.execute(
        select(func.count(func.distinct(AppEvent.user_id))).where(
            AppEvent.user_id.isnot(None),
            AppEvent.name.in_(tuple(CORE_ACTION_EVENTS) + (EV_ACTIVATION,)),
            (AppEvent.session_id.is_(None)) | (AppEvent.session_id != _BACKFILL_SESSION),
        )
    )).scalar() or 0

    # paid = 성공 결제가 1건이라도 있는 distinct 사용자 (생애 전환)
    paid = (await db.execute(
        select(func.count(func.distinct(PaymentHistory.user_id))).where(
            PaymentHistory.status == "success",
        )
    )).scalar() or 0

    # ── 리텐션/재방문용 데이터: 윈도 내 코호트 + 활동일을 메모리로 ───────────────
    window_start = now - timedelta(days=RETENTION_WINDOW_DAYS + 30)
    today = _local_date(now)

    cohort_rows = (await db.execute(
        select(User.id, User.created_at).where(
            User.status != "deleted",
            User.created_at >= window_start,
        )
    )).all()
    signup_day: dict[uuid.UUID, date] = {
        uid: _local_date(created) for uid, created in cohort_rows if created is not None
    }

    activity_rows = (await db.execute(
        select(AppEvent.user_id, AppEvent.created_at).where(
            AppEvent.user_id.isnot(None),
            AppEvent.created_at >= window_start,
            (AppEvent.session_id.is_(None)) | (AppEvent.session_id != _BACKFILL_SESSION),
        )
    )).all()
    activity_days: dict[uuid.UUID, set[date]] = {}
    for uid, created in activity_rows:
        if created is None:
            continue
        activity_days.setdefault(uid, set()).add(_local_date(created))

    # return = 가입일 이후의 다른 날에 활동 기록이 있는 distinct 사용자
    returned = sum(
        1 for uid, sday in signup_day.items()
        if any(d > sday for d in activity_days.get(uid, ()))
    )

    signup = int(signup)
    activation = int(activation)
    paid = int(paid)

    activation_rate = round(activation / signup * 100, 1) if signup else 0.0
    conversion_rate = round(paid / signup * 100, 1) if signup else 0.0

    d1 = _retention_from_maps(signup_day, activity_days, today, 1)
    d7 = _retention_from_maps(signup_day, activity_days, today, 7)
    d30 = _retention_from_maps(signup_day, activity_days, today, 30)

    return {
        "funnel": {
            "signup": signup,
            "activation": activation,
            "return": returned,
            "paid": paid,
        },
        "activation_rate": activation_rate,
        "conversion_rate": conversion_rate,
        "retention_d1": d1["rate"],
        "retention_d7": d7["rate"],
        "retention_d30": d30["rate"],
        "retention_detail": {"d1": d1, "d7": d7, "d30": d30},
    }
