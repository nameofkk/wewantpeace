"""
/admin/* 어드민 전용 API (role=admin만 접근 가능)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.core.redis import get_redis
from backend.app.models.user import User
from backend.app.models.community import Post, Report, AdminLog
from backend.app.models.subscription import Subscription, PaymentHistory

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SETTINGS_KEY = "admin:settings:v1"


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(403, detail="관리자만 접근 가능합니다.")
    return current_user


async def _log_action(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str = None,
    target_id: str = None,
    detail: dict = None,
):
    log = AdminLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(log)
    await db.flush()


# ── 통계 ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = (await db.execute(select(func.count()).select_from(User).where(User.status != "deleted"))).scalar()
    new_today = (await db.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))).scalar()
    dau = (await db.execute(select(func.count()).select_from(User).where(User.last_active >= today_start))).scalar()
    subscribers = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == "active")
    )).scalar()

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = (await db.execute(
        select(func.coalesce(func.sum(PaymentHistory.amount), 0))
        .where(PaymentHistory.status == "success", PaymentHistory.created_at >= month_start)
    )).scalar() or 0

    pending_reports = (await db.execute(
        select(func.count()).select_from(Report).where(Report.status == "pending")
    )).scalar()

    return {
        "total_users": total_users,
        "new_today": new_today,
        "dau": dau,
        "subscribers": subscribers,
        "monthly_revenue": monthly_revenue,
        "pending_reports": pending_reports,
    }


# ── 사용자 관리 ───────────────────────────────────────────────────────────────

class UserPatch(BaseModel):
    plan: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    suspended_until: Optional[str] = None
    suspend_reason: Optional[str] = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where((User.email.ilike(f"%{search}%")) | (User.nickname.ilike(f"%{search}%")))
    if status:
        q = q.where(User.status == status)
    if plan:
        q = q.where(User.plan == plan)
    q = q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "nickname": u.nickname,
            "plan": u.plan,
            "status": u.status,
            "role": u.role,
            "created_at": u.created_at.isoformat(),
            "last_active": u.last_active.isoformat(),
        }
        for u in users
    ]


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404)
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "display_name": user.display_name,
        "plan": user.plan,
        "status": user.status,
        "role": user.role,
        "birth_year": user.birth_year,
        "bio": user.bio,
        "created_at": user.created_at.isoformat(),
        "last_active": user.last_active.isoformat(),
        "agreed_terms_at": user.agreed_terms_at.isoformat() if user.agreed_terms_at else None,
        "suspend_reason": user.suspend_reason,
        "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404)

    changes = {}
    if body.plan is not None:
        user.plan = body.plan
        changes["plan"] = body.plan
    if body.status is not None:
        user.status = body.status
        changes["status"] = body.status
    if body.role is not None:
        user.role = body.role
        changes["role"] = body.role
    if body.suspended_until is not None:
        user.suspended_until = datetime.fromisoformat(body.suspended_until)
        changes["suspended_until"] = body.suspended_until
    if body.suspend_reason is not None:
        user.suspend_reason = body.suspend_reason
        changes["suspend_reason"] = body.suspend_reason

    await db.flush()
    await _log_action(db, admin, "update_user", "user", user_id, changes)
    return {"status": "ok"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404)
    user.status = "deleted"
    await db.flush()
    await _log_action(db, admin, "delete_user", "user", user_id)


# ── 신고 관리 ─────────────────────────────────────────────────────────────────

class ReportAction(BaseModel):
    status: str  # resolved | dismissed
    hide_content: bool = False


@router.get("/reports")
async def list_reports(
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(Report.status == status)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * 20).limit(20)
    )
    reports = result.scalars().all()
    return [
        {
            "id": r.id,
            "reporter_id": str(r.reporter_id) if r.reporter_id else None,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.patch("/reports/{report_id}")
async def handle_report(
    report_id: int,
    body: ReportAction,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404)

    report.status = body.status
    report.reviewed_at = datetime.now(timezone.utc)
    report.reviewed_by = admin.id

    # 콘텐츠 숨김 처리
    if body.hide_content and report.target_type == "post":
        try:
            pr = await db.execute(select(Post).where(Post.id == uuid.UUID(report.target_id)))
            post = pr.scalar_one_or_none()
            if post:
                post.status = "hidden"
        except Exception:
            pass

    await db.flush()
    await _log_action(db, admin, "handle_report", "report", str(report_id), {"status": body.status})
    return {"status": "ok"}


# ── 게시글 관리 ───────────────────────────────────────────────────────────────

@router.get("/posts")
async def list_admin_posts(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Post)
    if status:
        q = q.where(Post.status == status)
    if search:
        q = q.where(Post.title.ilike(f"%{search}%"))
    q = q.order_by(Post.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    posts = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "post_type": p.post_type,
            "status": p.status,
            "view_count": p.view_count,
            "like_count": p.like_count,
            "comment_count": p.comment_count,
            "created_at": p.created_at.isoformat(),
        }
        for p in posts
    ]


@router.patch("/posts/{post_id}/hide")
async def hide_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Post).where(Post.id == uuid.UUID(post_id)))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)
    post.status = "hidden" if post.status == "active" else "active"
    await db.flush()
    await _log_action(db, admin, "hide_post", "post", post_id, {"new_status": post.status})
    return {"status": post.status}


# ── 구독 현황 ─────────────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription).order_by(Subscription.created_at.desc())
        .offset((page - 1) * 20).limit(20)
    )
    subs = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "plan": s.plan,
            "status": s.status,
            "amount": s.amount,
            "started_at": s.started_at.isoformat(),
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "next_billing_at": s.next_billing_at.isoformat() if s.next_billing_at else None,
        }
        for s in subs
    ]


# ── 앱 설정 ──────────────────────────────────────────────────────────────────

class AppSettings(BaseModel):
    maintenance_mode: bool = False
    allow_signup: bool = True
    pro_price: int = 4900
    pro_plus_price: int = 9900
    notice_banner: str = ""


@router.get("/settings")
async def get_settings(admin: User = Depends(require_admin)):
    import json
    try:
        redis = get_redis()
        cached = await redis.get(ADMIN_SETTINGS_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return AppSettings().dict()


@router.patch("/settings")
async def update_settings(
    body: AppSettings,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import json
    try:
        redis = get_redis()
        await redis.set(ADMIN_SETTINGS_KEY, json.dumps(body.dict()))
    except Exception:
        pass
    await _log_action(db, admin, "update_settings", detail=body.dict())
    return body
