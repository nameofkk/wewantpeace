"""
/me/* 사용자 API.

GET/POST/DELETE /me/areas          관심지역 CRUD (Free: 국가 2개 제한)
GET/PATCH       /me/preferences    알림 설정
POST            /me/push-tokens    FCM 토큰 등록
DELETE          /me/push-tokens    FCM 토큰 삭제
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, time as dt_time
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, get_db, _PLAN_ORDER
from backend.app.models.user import User, UserArea, UserPushToken, UserPreference
from backend.app.models.notification import Notification
from backend.app.models.paywall_event import PaywallEvent
from backend.app.models.app_event import AppEvent

router = APIRouter(prefix="/me", tags=["me"])

FREE_AREA_LIMIT = 2
PRO_AREA_LIMIT = 5


# ── Pydantic 스키마 ───────────────────────────────────────────────────────────

class AreaCreate(BaseModel):
    area_type: str = "country"
    country_code: Optional[str] = None
    label: Optional[str] = None
    notify_verified: bool = True
    notify_fast: bool = True  # v7: 모든 플랜에서 기본 활성화


class AreaOut(BaseModel):
    id: int
    area_type: str
    country_code: Optional[str]
    label: Optional[str]
    notify_verified: bool
    notify_fast: bool
    is_active: bool
    created_at: str


class PreferencesOut(BaseModel):
    language: str
    min_severity: int
    min_kscore: float
    topics: list[str]
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    timezone: str
    home_country: str = ""


class PreferencesPatch(BaseModel):
    language: Optional[str] = None
    min_severity: Optional[int] = None
    min_kscore: Optional[float] = None
    topics: Optional[list[str]] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    home_country: Optional[str] = None


class PushTokenCreate(BaseModel):
    fcm_token: str
    platform: str = "web"


class UserOut(BaseModel):
    id: str
    firebase_uid: str
    plan: str
    role: str
    email: Optional[str]
    nickname: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    agreed_terms_at: Optional[str] = None


class EventBody(BaseModel):
    name: str
    props: dict = {}
    session_id: Optional[str] = None
    platform: str = "web"


class PaywallEventBody(BaseModel):
    trigger: str
    action: str  # shown|dismissed|clicked_upgrade
    source: Optional[str] = None
    plan: Optional[str] = None
    session_id: Optional[str] = None


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _area_to_out(a: UserArea) -> AreaOut:
    return AreaOut(
        id=a.id,
        area_type=a.area_type,
        country_code=a.country_code,
        label=a.label,
        notify_verified=a.notify_verified,
        notify_fast=a.notify_fast,
        is_active=a.is_active,
        created_at=a.created_at.isoformat(),
    )


def _pref_to_out(p: UserPreference) -> PreferencesOut:
    return PreferencesOut(
        language=p.language,
        min_severity=p.min_severity,
        min_kscore=p.min_kscore,
        topics=p.topics or [],
        quiet_hours_start=p.quiet_hours_start.isoformat() if p.quiet_hours_start else None,
        quiet_hours_end=p.quiet_hours_end.isoformat() if p.quiet_hours_end else None,
        timezone=p.timezone,
        home_country=getattr(p, "home_country", "KR"),
    )


# ── /me (내 정보) ─────────────────────────────────────────────────────────────

@router.get("", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=str(current_user.id),
        firebase_uid=current_user.firebase_uid,
        plan=current_user.plan,
        role=current_user.role or "user",
        email=current_user.email,
        nickname=current_user.nickname,
        display_name=current_user.display_name,
        bio=current_user.bio,
        agreed_terms_at=current_user.agreed_terms_at.isoformat() if current_user.agreed_terms_at else None,
    )


# ── /me/areas ─────────────────────────────────────────────────────────────────

@router.get("/areas", response_model=list[AreaOut])
async def list_areas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArea).where(UserArea.user_id == current_user.id)
        .order_by(UserArea.created_at.asc())
    )
    return [_area_to_out(a) for a in result.scalars().all()]


@router.post("/areas", response_model=AreaOut, status_code=201)
async def create_area(
    body: AreaCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 플랜별 관심지역 개수 제한 (비활성 국가 제외)
    count_result = await db.execute(
        select(func.count()).select_from(UserArea)
        .where(UserArea.user_id == current_user.id, UserArea.is_active == True)
    )
    count = count_result.scalar() or 0
    plan = current_user.plan.lower()
    if plan == "free" and count >= FREE_AREA_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FREE_AREA_LIMIT",
                "limit": FREE_AREA_LIMIT,
                "upgrade_url": "/upgrade",
            },
        )
    if plan == "pro" and count >= PRO_AREA_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PRO_AREA_LIMIT",
                "limit": PRO_AREA_LIMIT,
                "upgrade_url": "/upgrade",
            },
        )

    # v7: notify_fast는 모든 플랜에서 허용 (신속 알림)
    # notify_verified는 Pro 이상만 허용 (신뢰 알림)
    if body.notify_verified and _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
        raise HTTPException(
            status_code=403,
            detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "notify_verified"},
        )

    # 중복 방지: 같은 country_code가 이미 있으면 기존 레코드 반환
    cc = body.country_code.upper() if body.country_code else None
    if cc:
        existing = await db.execute(
            select(UserArea).where(
                UserArea.user_id == current_user.id,
                UserArea.country_code == cc,
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return _area_to_out(found)

    area = UserArea(
        user_id=current_user.id,
        area_type=body.area_type,
        country_code=cc,
        label=body.label,
        notify_verified=body.notify_verified,
        notify_fast=body.notify_fast,
    )
    db.add(area)
    await db.flush()

    # 플랜에 맞게 is_active 동기화 (플랜 변경 후 미동기화 상태 복구 포함)
    from backend.app.services.area_activation import sync_area_activation
    await sync_area_activation(current_user.id, current_user.plan, db)

    # flush 후 area 다시 읽기 (is_active가 sync에 의해 변경되었을 수 있음)
    await db.refresh(area)
    return _area_to_out(area)


@router.patch("/areas/{area_id}", response_model=AreaOut)
async def update_area(
    area_id: int,
    body: AreaCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArea).where(
            UserArea.id == area_id,
            UserArea.user_id == current_user.id,
        )
    )
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=404, detail={"code": "AREA_NOT_FOUND"})

    if not area.is_active:
        raise HTTPException(
            status_code=403,
            detail={"code": "AREA_INACTIVE", "upgrade_url": "/upgrade"},
        )

    if body.notify_verified is not None:
        area.notify_verified = body.notify_verified
    if body.notify_fast is not None:
        area.notify_fast = body.notify_fast
    if body.label is not None:
        area.label = body.label

    await db.flush()
    return _area_to_out(area)


@router.delete("/areas/{area_id}", status_code=204)
async def delete_area(
    area_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArea).where(
            UserArea.id == area_id,
            UserArea.user_id == current_user.id,
        )
    )
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=404, detail={"code": "AREA_NOT_FOUND"})

    await db.delete(area)
    await db.flush()


# ── /me/preferences ───────────────────────────────────────────────────────────

@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
        await db.flush()
    return _pref_to_out(pref)


@router.patch("/preferences", response_model=PreferencesOut)
async def update_preferences(
    body: PreferencesPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
        await db.flush()

    # v7: notify_fast는 모든 플랜에서 가능 (제한 제거)
    # notify_verified_global은 Pro 이상만 가능
    if getattr(body, "notify_verified_global", None) is True:
        if _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "notify_verified"},
            )

    if body.language is not None:
        pref.language = body.language
    if body.min_severity is not None:
        pref.min_severity = body.min_severity
    if body.min_kscore is not None:
        # Free 플랜은 4.0 고정, Pro는 3.0~10.0, Pro+는 1.5~10.0 (0-10 스케일)
        plan_lower = current_user.plan.lower()
        min_allowed = 4.0 if plan_lower == "free" else (1.5 if plan_lower == "pro_plus" else 3.0)
        pref.min_kscore = max(min_allowed, min(body.min_kscore, 10.0))
    if body.topics is not None:
        # 토픽 필터는 Pro 이상만 허용
        if body.topics and _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "topics"},
            )
        pref.topics = body.topics
    if body.timezone is not None:
        from zoneinfo import available_timezones
        if body.timezone and body.timezone not in available_timezones():
            raise HTTPException(400, detail={"code": "INVALID_TIMEZONE", "value": body.timezone})
        pref.timezone = body.timezone
    # quiet_hours: "" = 해제, "HH:MM" = 설정 (Pro 이상만 허용)
    if body.quiet_hours_start is not None:
        from datetime import time as dt_time
        if body.quiet_hours_start == "":
            pref.quiet_hours_start = None
        elif _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "quiet_hours"},
            )
        else:
            try:
                parts = body.quiet_hours_start.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                pref.quiet_hours_start = dt_time(h, m)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail={"code": "INVALID_FORMAT", "field": "quiet_hours_start", "expected": "HH:MM"})
    if body.quiet_hours_end is not None:
        from datetime import time as dt_time
        if body.quiet_hours_end == "":
            pref.quiet_hours_end = None
        elif _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "quiet_hours"},
            )
        else:
            try:
                parts = body.quiet_hours_end.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                pref.quiet_hours_end = dt_time(h, m)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail={"code": "INVALID_FORMAT", "field": "quiet_hours_end", "expected": "HH:MM"})

    if body.home_country is not None:
        new_hc = body.home_country.strip()
        if new_hc == "":
            # BASIC 모드: 빈 문자열 허용 (raw KScore, 모든 플랜)
            pref.home_country = ""
        else:
            if len(new_hc) != 2 or not new_hc.isalpha():
                raise HTTPException(400, detail={"code": "INVALID_COUNTRY_CODE"})
            new_hc = new_hc.upper()
            # Free 플랜은 BASIC 모드(빈 문자열)만 허용, 기준국가 변경 불가
            if current_user.plan.lower() == "free":
                raise HTTPException(
                    status_code=403,
                    detail={"code": "PLAN_REQUIRED", "required": "pro", "feature": "home_country"},
                )
            pref.home_country = new_hc

    await db.flush()
    return _pref_to_out(pref)


# ── /me/push-tokens ───────────────────────────────────────────────────────────

@router.post("/push-tokens", status_code=201)
async def register_push_token(
    body: PushTokenCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 이미 존재하면 last_used 갱신
    result = await db.execute(
        select(UserPushToken).where(
            UserPushToken.user_id == current_user.id,
            UserPushToken.fcm_token == body.fcm_token,
        )
    )
    token = result.scalar_one_or_none()

    if token:
        from datetime import datetime, timezone
        token.last_used = datetime.now(timezone.utc)
        token.last_seen_at = datetime.now(timezone.utc)
        token.status = "active"
    else:
        from datetime import datetime, timezone
        token = UserPushToken(
            user_id=current_user.id,
            fcm_token=body.fcm_token,
            platform=body.platform,
            status="active",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(token)

    await db.flush()
    return {"status": "ok", "platform": body.platform}


@router.delete("/push-tokens")
async def delete_push_token(
    fcm_token: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(UserPushToken)
        .where(
            UserPushToken.user_id == current_user.id,
            UserPushToken.fcm_token == fcm_token,
        )
        .values(status="revoked")
    )
    await db.flush()
    return {"status": "ok"}


# ── /me/notifications ────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    type: str
    cluster_id: Optional[str]
    title: str
    body: str
    is_read: bool
    feedback: Optional[str] = None
    created_at: str


def _notif_to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        cluster_id=str(n.cluster_id) if n.cluster_id else None,
        title=n.title,
        body=n.body,
        is_read=n.is_read,
        feedback=n.feedback,
        created_at=n.created_at.isoformat(),
    )


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    limit: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
    )
    return [_notif_to_out(n) for n in result.scalars().all()]


@router.get("/notifications/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    count = result.scalar() or 0
    return {"unread": count}


@router.patch("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail={"code": "NOTIFICATION_NOT_FOUND"})
    notif.is_read = True
    await db.flush()
    return {"status": "ok"}


@router.patch("/notifications/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.flush()
    return {"status": "ok"}


class FeedbackBody(BaseModel):
    feedback: str  # "thumbs_up" | "thumbs_down"


@router.patch("/notifications/{notif_id}/feedback")
async def submit_feedback(
    notif_id: int,
    body: FeedbackBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.feedback not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=400, detail="feedback must be 'thumbs_up' or 'thumbs_down'")

    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail={"code": "NOTIFICATION_NOT_FOUND"})
    notif.feedback = body.feedback
    await db.flush()
    return {"status": "ok"}


# ── /me/paywall-cap ──────────────────────────────────────────────────────────

DAILY_PAYWALL_CAP = 2


class PaywallCapOut(BaseModel):
    shown_today: int
    daily_cap: int
    remaining: int


@router.get("/paywall-cap", response_model=PaywallCapOut)
async def get_paywall_cap(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """오늘(UTC) paywall shown 횟수와 잔여 노출 가능 횟수 반환."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    result = await db.execute(
        select(func.count())
        .select_from(PaywallEvent)
        .where(
            PaywallEvent.user_id == current_user.id,
            PaywallEvent.action == "shown",
            PaywallEvent.created_at >= today_start,
        )
    )
    shown_today = result.scalar() or 0
    remaining = max(0, DAILY_PAYWALL_CAP - shown_today)
    return PaywallCapOut(
        shown_today=shown_today,
        daily_cap=DAILY_PAYWALL_CAP,
        remaining=remaining,
    )


# ── /me/events & /me/paywall-event ───────────────────────────────────────────

logger = structlog.get_logger()


@router.post("/events", status_code=201)
async def track_event(
    body: EventBody,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Generic event tracking endpoint. Works for both authenticated and anonymous users."""
    user_id = current_user.id if current_user else None
    logger.info("track_event", user_id=str(user_id) if user_id else "anon", event=body.name, props=body.props)

    # Save to app_events (all events)
    ae = AppEvent(
        user_id=user_id,
        session_id=body.session_id,
        name=body.name,
        props=body.props or None,
        platform=body.platform,
    )
    db.add(ae)

    # paywall events also go to dedicated table (authenticated only)
    if body.name.startswith("paywall_") and current_user:
        pe = PaywallEvent(
            user_id=current_user.id,
            trigger=body.props.get("trigger", body.name),
            action=body.props.get("action", body.name),
            source=body.props.get("source"),
            plan=body.props.get("plan"),
            session_id=body.props.get("session_id"),
        )
        db.add(pe)

    await db.flush()
    return {"status": "ok"}


@router.post("/paywall-event", status_code=201)
async def track_paywall_event(
    body: PaywallEventBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dedicated paywall event tracking."""
    from backend.app.models.paywall_event import PaywallEvent
    pe = PaywallEvent(
        user_id=current_user.id,
        trigger=body.trigger,
        action=body.action,
        source=body.source,
        plan=body.plan,
        session_id=body.session_id,
    )
    db.add(pe)
    await db.flush()
    logger.info("paywall_event", user_id=str(current_user.id), trigger=body.trigger, action=body.action)
    return {"status": "ok"}


# ── /me/missed-alerts (v7: missed-spikes → missed-alerts) ─────────────────

class MissedAlertOut(BaseModel):
    id: str
    cluster_id: str
    reason: str
    created_at: str


# 하위호환: /me/missed-spikes 경로도 유지
MissedSpikeOut = MissedAlertOut


@router.get("/missed-alerts", response_model=list[MissedAlertOut])
@router.get("/missed-spikes", response_model=list[MissedAlertOut], include_in_schema=False)
async def list_missed_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """놓친 알림 목록 (is_shown=False, 최근 30개)."""
    from backend.app.models.user_missed_spike import UserMissedAlertSummary

    result = await db.execute(
        select(UserMissedAlertSummary)
        .where(
            UserMissedAlertSummary.user_id == current_user.id,
            UserMissedAlertSummary.is_shown == False,
        )
        .order_by(UserMissedAlertSummary.created_at.desc())
        .limit(30)
    )
    return [
        MissedAlertOut(
            id=str(s.id),
            cluster_id=str(s.cluster_id),
            reason=s.reason,
            created_at=s.created_at.isoformat(),
        )
        for s in result.scalars().all()
    ]


@router.patch("/missed-alerts/{alert_id}/shown")
@router.patch("/missed-spikes/{alert_id}/shown", include_in_schema=False)
async def mark_missed_alert_shown(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """놓친 알림을 '확인 완료'로 표시."""
    import uuid as _uuid
    from backend.app.models.user_missed_spike import UserMissedAlertSummary

    result = await db.execute(
        select(UserMissedAlertSummary).where(
            UserMissedAlertSummary.id == _uuid.UUID(alert_id),
            UserMissedAlertSummary.user_id == current_user.id,
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail={"code": "MISSED_ALERT_NOT_FOUND"})
    summary.is_shown = True
    await db.flush()
    return {"status": "ok"}


# ── /me/upgrade-prompt ────────────────────────────────────────────────────────

@router.get("/upgrade-prompt")
async def check_upgrade_prompt(
    current_user: User = Depends(get_current_user),
):
    """
    Spike 알림 3회 이상 받은 FREE 유저에게 Pro 업그레이드 프롬프트 표시 여부 반환.
    Redis key: spike_push_count:{user_id} (30일 TTL, worker push_service에서 증가)
    """
    if current_user.plan != "free":
        return {"show": False, "spike_count": 0}

    try:
        from backend.app.core.redis import get_redis
        redis = get_redis()
        count = await redis.get(f"spike_push_count:{current_user.id}")
        spike_count = int(count or 0)
        return {"show": spike_count >= 3, "spike_count": spike_count}
    except Exception:
        return {"show": False, "spike_count": 0}


# ── /me/referral ─────────────────────────────────────────────────────────────

import secrets
import string


def _generate_referral_code() -> str:
    """8자리 대문자+숫자 레퍼럴 코드 생성."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


@router.get("/referral")
async def get_referral(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 레퍼럴 코드 + 초대 현황 조회. 코드 없으면 자동 생성."""
    from sqlalchemy import text

    # 코드 없으면 생성
    if not current_user.referral_code:
        for _ in range(5):  # collision retry
            code = _generate_referral_code()
            existing = await db.execute(select(User).where(User.referral_code == code))
            if not existing.scalar_one_or_none():
                current_user.referral_code = code
                await db.flush()
                break

    # 초대 현황
    rewards_q = await db.execute(
        text("""
            SELECT rr.referee_id, rr.reward_type, rr.rewarded_at, rr.referee_activated_at, rr.created_at,
                   u.nickname, u.display_name
            FROM referral_rewards rr
            JOIN users u ON u.id = rr.referee_id
            WHERE rr.referrer_id = :uid
            ORDER BY rr.created_at DESC
        """),
        {"uid": str(current_user.id)},
    )
    rewards = [
        {
            "referee_name": row.display_name or row.nickname or "User",
            "reward_type": row.reward_type,
            "rewarded": row.rewarded_at is not None,
            "activated": row.referee_activated_at is not None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rewards_q.all()
    ]

    return {
        "referral_code": current_user.referral_code,
        "referral_url": f"https://www.wewantpeace.live/?ref={current_user.referral_code}",
        "total_invited": len(rewards),
        "total_activated": sum(1 for r in rewards if r["activated"]),
        "rewards": rewards,
    }
