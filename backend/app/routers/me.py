"""
/me/* 사용자 API.

GET/POST/DELETE /me/areas          관심지역 CRUD (Free: 국가 2개 제한)
GET/PATCH       /me/preferences    알림 설정
POST            /me/push-tokens    FCM 토큰 등록
DELETE          /me/push-tokens    FCM 토큰 삭제
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db, _PLAN_ORDER
from backend.app.models.user import User, UserArea, UserPushToken, UserPreference
from backend.app.models.notification import Notification

router = APIRouter(prefix="/me", tags=["me"])

FREE_AREA_LIMIT = 2
PRO_AREA_LIMIT = 5


# ── Pydantic 스키마 ───────────────────────────────────────────────────────────

class AreaCreate(BaseModel):
    area_type: str = "country"
    country_code: Optional[str] = None
    label: Optional[str] = None
    notify_verified: bool = True
    notify_fast: bool = False


class AreaOut(BaseModel):
    id: int
    area_type: str
    country_code: Optional[str]
    label: Optional[str]
    notify_verified: bool
    notify_fast: bool
    created_at: str


class PreferencesOut(BaseModel):
    language: str
    min_severity: int
    min_kscore: float
    topics: list[str]
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    timezone: str


class PreferencesPatch(BaseModel):
    language: Optional[str] = None
    min_severity: Optional[int] = None
    min_kscore: Optional[float] = None
    topics: Optional[list[str]] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None


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


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _area_to_out(a: UserArea) -> AreaOut:
    return AreaOut(
        id=a.id,
        area_type=a.area_type,
        country_code=a.country_code,
        label=a.label,
        notify_verified=a.notify_verified,
        notify_fast=a.notify_fast,
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
    # 플랜별 관심지역 개수 제한
    count_result = await db.execute(
        select(func.count()).select_from(UserArea)
        .where(UserArea.user_id == current_user.id)
    )
    count = count_result.scalar() or 0
    plan = current_user.plan.lower()
    if plan == "free" and count >= FREE_AREA_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FREE_AREA_LIMIT",
                "message": f"Free 플랜은 관심지역 {FREE_AREA_LIMIT}개까지 가능합니다.",
                "upgrade_url": "/upgrade",
            },
        )
    if plan == "pro" and count >= PRO_AREA_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PRO_AREA_LIMIT",
                "message": f"Pro 플랜은 관심지역 {PRO_AREA_LIMIT}개까지 가능합니다. Pro+로 업그레이드하세요.",
                "upgrade_url": "/upgrade",
            },
        )

    # notify_fast는 Pro 이상만 허용
    if body.notify_fast and _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
        raise HTTPException(
            status_code=403,
            detail={"code": "PLAN_REQUIRED", "required": "pro", "message": "Fast 알림은 Pro 플랜 전용입니다."},
        )

    area = UserArea(
        user_id=current_user.id,
        area_type=body.area_type,
        country_code=body.country_code.upper() if body.country_code else None,
        label=body.label,
        notify_verified=body.notify_verified,
        notify_fast=body.notify_fast,
    )
    db.add(area)
    await db.flush()
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
        raise HTTPException(status_code=404, detail="관심지역을 찾을 수 없습니다.")

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
        raise HTTPException(status_code=404, detail="관심지역을 찾을 수 없습니다.")

    db.delete(area)
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

    # notify_fast는 Pro 이상만 가능
    if getattr(body, "notify_fast_global", None) is True:
        if _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "message": "Fast 알림은 Pro 플랜 전용입니다."},
            )

    if body.language is not None:
        pref.language = body.language
    if body.min_severity is not None:
        pref.min_severity = body.min_severity
    if body.min_kscore is not None:
        # Free 플랜은 3.0 고정, Pro는 3.0~10.0, Pro+는 1.5~10.0 (0-10 스케일)
        plan_lower = current_user.plan.lower()
        min_allowed = 3.0 if plan_lower == "free" else (1.5 if plan_lower == "pro_plus" else 3.0)
        pref.min_kscore = max(min_allowed, min(body.min_kscore, 10.0))
    if body.topics is not None:
        # 토픽 필터는 Pro 이상만 허용
        if body.topics and _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "message": "토픽 필터는 Pro 플랜 전용입니다."},
            )
        pref.topics = body.topics
    if body.timezone is not None:
        pref.timezone = body.timezone
    # quiet_hours: "" = 해제, "HH:MM" = 설정 (Pro 이상만 허용)
    if body.quiet_hours_start is not None:
        from datetime import time as dt_time
        if body.quiet_hours_start == "":
            pref.quiet_hours_start = None
        elif _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "message": "방해금지 시간은 Pro 플랜 전용입니다."},
            )
        else:
            try:
                parts = body.quiet_hours_start.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                pref.quiet_hours_start = dt_time(h, m)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="quiet_hours_start 형식 오류: HH:MM")
    if body.quiet_hours_end is not None:
        from datetime import time as dt_time
        if body.quiet_hours_end == "":
            pref.quiet_hours_end = None
        elif _PLAN_ORDER.get(current_user.plan.lower(), 0) < _PLAN_ORDER.get("pro", 1):
            raise HTTPException(
                status_code=403,
                detail={"code": "PLAN_REQUIRED", "required": "pro", "message": "방해금지 시간은 Pro 플랜 전용입니다."},
            )
        else:
            try:
                parts = body.quiet_hours_end.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                pref.quiet_hours_end = dt_time(h, m)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="quiet_hours_end 형식 오류: HH:MM")

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
    else:
        token = UserPushToken(
            user_id=current_user.id,
            fcm_token=body.fcm_token,
            platform=body.platform,
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
    await db.execute(
        delete(UserPushToken).where(
            UserPushToken.user_id == current_user.id,
            UserPushToken.fcm_token == fcm_token,
        )
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
    created_at: str


def _notif_to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        cluster_id=str(n.cluster_id) if n.cluster_id else None,
        title=n.title,
        body=n.body,
        is_read=n.is_read,
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
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
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
