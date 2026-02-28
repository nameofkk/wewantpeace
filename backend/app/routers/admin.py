"""
/admin/* 어드민 전용 API (role=admin만 접근 가능)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_, cast, Date, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db, require_admin
from backend.app.core.redis import get_redis
from backend.app.models.user import User, UserPushToken
from backend.app.models.community import Post, Report, AdminLog, Feedback
from backend.app.models.subscription import Subscription, PaymentHistory
from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.tension_index import TensionIndex
from backend.app.models.raw_event import RawEvent
from backend.app.models.source_channel import SourceChannel
from backend.app.models.trending_keyword import TrendingKeyword

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SETTINGS_KEY = "admin:settings:v1"


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

    # 활성 클러스터 수
    active_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.severity > 0)
    )).scalar() or 0

    # 오늘 수집된 이벤트 수
    events_today = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= today_start)
    )).scalar() or 0

    # 위기 국가 수 (tension_level=3)
    crisis_countries_q = await db.execute(
        select(TensionIndex.country_code)
        .where(TensionIndex.tension_level == 3)
        .group_by(TensionIndex.country_code)
    )
    crisis_countries = len(crisis_countries_q.all())

    # 활성 푸시 토큰 수
    push_tokens = (await db.execute(
        select(func.count()).select_from(UserPushToken)
    )).scalar() or 0

    # ── 데이터 품질 KPI (최근 24시간) ──
    cutoff_24h = now - timedelta(hours=24)

    events_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h)
    )).scalar() or 0

    unclassified_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.topic == "unknown")
    )).scalar() or 0

    translation_fail_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.title_ko == None)
    )).scalar() or 0

    geo_fail_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.country_code == None)
    )).scalar() or 0

    unclassified_rate = round(unclassified_24h / max(1, events_24h) * 100, 1)
    translation_fail_rate = round(translation_fail_24h / max(1, events_24h) * 100, 1)
    geo_fail_rate = round(geo_fail_24h / max(1, events_24h) * 100, 1)

    return {
        "total_users": total_users,
        "new_today": new_today,
        "dau": dau,
        "subscribers": subscribers,
        "monthly_revenue": monthly_revenue,
        "pending_reports": pending_reports,
        "active_clusters": active_clusters,
        "events_today": events_today,
        "crisis_countries": crisis_countries,
        "push_tokens": push_tokens,
        # 데이터 품질
        "unclassified_rate": unclassified_rate,
        "translation_fail_rate": translation_fail_rate,
        "geo_fail_rate": geo_fail_rate,
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
    exclude_status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if search:
        filters.append((User.email.ilike(f"%{search}%")) | (User.nickname.ilike(f"%{search}%")))
    if status:
        filters.append(User.status == status)
    if exclude_status:
        filters.append(User.status != exclude_status)
    if plan:
        filters.append(User.plan == plan)

    # total count
    count_q = select(func.count(User.id))
    if filters:
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar() or 0

    # paginated rows
    q = select(User)
    if filters:
        q = q.where(and_(*filters))
    q = q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    users = result.scalars().all()

    return {
        "total": total,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "nickname": u.nickname,
                "display_name": u.display_name,
                "plan": u.plan,
                "status": u.status,
                "role": u.role,
                "created_at": u.created_at.isoformat(),
                "last_active": u.last_active.isoformat() if u.last_active else None,
            }
            for u in users
        ],
    }


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
        # 어드민이 free로 변경 시 활성 구독도 취소 (웹훅이 플랜 복원하는 버그 방지)
        if body.plan == "free":
            active_subs = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.status == "active",
                )
            )
            for sub in active_subs.scalars().all():
                sub.status = "cancelled"
                changes.setdefault("cancelled_subscriptions", []).append(str(sub.id))
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
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Report)
    if status:
        q = q.where(Report.status == status)
    q = q.order_by(Report.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    reports = result.scalars().all()

    # reporter nickname 조회
    reporter_ids = [r.reporter_id for r in reports if r.reporter_id]
    nickname_map: dict[uuid.UUID, str] = {}
    if reporter_ids:
        user_result = await db.execute(
            select(User.id, User.nickname).where(User.id.in_(reporter_ids))
        )
        nickname_map = {row.id: row.nickname for row in user_result.all()}

    return [
        {
            "id": r.id,
            "reporter_nickname": nickname_map.get(r.reporter_id) if r.reporter_id else None,
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
    from sqlalchemy.orm import selectinload

    q = select(Post)
    filters = []
    if status:
        filters.append(Post.status == status)
    if search:
        filters.append(Post.title.ilike(f"%{search}%"))
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Post.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    posts = result.scalars().all()

    # author nickname 조회 (User join)
    user_ids = [p.user_id for p in posts if p.user_id]
    nickname_map: dict[uuid.UUID, str] = {}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.nickname).where(User.id.in_(user_ids))
        )
        nickname_map = {row.id: row.nickname for row in user_result.all()}

    return {
        "total": total,
        "items": [
            {
                "id": str(p.id),
                "title": p.title,
                "post_type": p.post_type,
                "status": p.status,
                "views": p.view_count,
                "likes": p.like_count,
                "comment_count": p.comment_count,
                "author_nickname": nickname_map.get(p.user_id) if p.user_id else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in posts
        ],
    }


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
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Subscription)
    if status:
        q = q.where(Subscription.status == status)
    if plan:
        q = q.where(Subscription.plan == plan)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Subscription.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    subs = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": str(s.id),
                "user_id": str(s.user_id),
                "plan": s.plan,
                "status": s.status,
                "amount": s.amount,
                "currency": s.currency,
                "platform": s.platform,
                "started_at": s.started_at.isoformat(),
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "next_billing_at": s.next_billing_at.isoformat() if s.next_billing_at else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in subs
        ],
    }


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


# ── 클러스터 관리 ───────────────────────────────────────────────────────────

class ClusterPatch(BaseModel):
    severity: Optional[int] = None
    topic: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/clusters")
async def list_clusters(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    severity: Optional[int] = Query(None),
    topic: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(IssueCluster)
    if search:
        q = q.where(
            (IssueCluster.title.ilike(f"%{search}%"))
            | (IssueCluster.title_ko.ilike(f"%{search}%"))
        )
    if severity is not None:
        q = q.where(IssueCluster.severity == severity)
    if topic:
        q = q.where(IssueCluster.topic == topic)
    if country:
        q = q.where(IssueCluster.country_code == country.upper())

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(IssueCluster.last_event_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    clusters = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(c.id),
                "title": c.title,
                "title_ko": c.title_ko,
                "country_code": c.country_code,
                "topic": c.topic,
                "severity": c.severity,
                "kscore": round(c.kscore, 2),
                "event_count": c.event_count,
                "confidence": round(c.confidence, 3),
                "is_spike": c.is_spike,
                "first_event_at": c.first_event_at.isoformat(),
                "last_event_at": c.last_event_at.isoformat(),
                "created_at": c.created_at.isoformat(),
            }
            for c in clusters
        ],
    }


@router.patch("/clusters/{cluster_id}")
async def update_cluster(
    cluster_id: str,
    body: ClusterPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IssueCluster).where(IssueCluster.id == uuid.UUID(cluster_id))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404)

    changes = {}
    if body.severity is not None:
        cluster.severity = body.severity
        changes["severity"] = body.severity
    if body.topic is not None:
        cluster.topic = body.topic
        changes["topic"] = body.topic
    if body.is_active is not None:
        # is_active → severity 0 으로 비활성화
        if not body.is_active:
            cluster.severity = 0
            changes["deactivated"] = True
        changes["is_active"] = body.is_active

    await db.flush()
    await _log_action(db, admin, "update_cluster", "cluster", cluster_id, changes)
    return {"status": "ok"}


@router.delete("/clusters/{cluster_id}", status_code=204)
async def delete_cluster(
    cluster_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IssueCluster).where(IssueCluster.id == uuid.UUID(cluster_id))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404)
    # soft delete: severity 0으로 설정
    cluster.severity = 0
    await db.flush()
    await _log_action(db, admin, "delete_cluster", "cluster", cluster_id)


# ── 이벤트 뷰어 ─────────────────────────────────────────────────────────────

@router.get("/events")
async def list_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    severity: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(NormalizedEvent).where(NormalizedEvent.is_duplicate == False)
    if source:
        q = q.where(NormalizedEvent.source_tier == source)
    if country:
        q = q.where(NormalizedEvent.country_code == country.upper())
    if severity is not None:
        q = q.where(NormalizedEvent.severity >= severity)
    if search:
        q = q.where(
            (NormalizedEvent.title.ilike(f"%{search}%"))
            | (NormalizedEvent.title_ko.ilike(f"%{search}%"))
        )

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(NormalizedEvent.event_time.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    events = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(e.id),
                "title": e.title,
                "title_ko": e.title_ko,
                "country_code": e.country_code,
                "topic": e.topic,
                "severity": e.severity,
                "source_tier": e.source_tier,
                "confidence": round(e.confidence, 3),
                "event_time": e.event_time.isoformat(),
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


# ── 긴장도 현황 ─────────────────────────────────────────────────────────────

@router.get("/tension")
async def list_tension(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전 국가 최신 긴장도."""
    raw_result = await db.execute(
        select(TensionIndex).order_by(TensionIndex.country_code, TensionIndex.time.desc())
    )
    all_rows = raw_result.scalars().all()
    tension_map: dict[str, TensionIndex] = {}
    for row in all_rows:
        if row.country_code not in tension_map:
            tension_map[row.country_code] = row

    return [
        {
            "country_code": t.country_code,
            "raw_score": round(t.raw_score, 1),
            "tension_level": t.tension_level,
            "percentile_30d": round(t.percentile_30d or 0.0, 1),
            "event_score": round(t.event_score or 0.0, 1),
            "accel_score": round(t.accel_score or 0.0, 1),
            "spillover_score": round(t.spillover_score or 0.0, 1),
            "updated_at": t.time.isoformat(),
        }
        for t in sorted(tension_map.values(), key=lambda x: x.raw_score, reverse=True)
    ]


@router.post("/tension/recalculate")
async def admin_tension_recalculate(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """긴장도 수동 재계산."""
    import logging
    _logger = logging.getLogger(__name__)
    from backend.app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as calc_db:
            async with calc_db.begin():
                from worker.processor.tension_calculator import calculate_all_tensions
                results = await calculate_all_tensions(calc_db)
                _logger.info("admin_tension_recalculate 완료: %d개국", len(results))
                await _log_action(db, admin, "tension_recalculate", detail={"countries": len(results)})
                return {"status": "ok", "countries": len(results)}
    except Exception as e:
        _logger.error("admin_tension_recalculate 실패: %s", e, exc_info=True)
        raise HTTPException(500, detail="긴장도 재계산 중 오류가 발생했습니다.")


@router.get("/trending")
async def admin_trending_list(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """현재 활성 트렌딩 키워드 전체 목록 (최신 calculated_at 기준)."""
    from sqlalchemy import text as sa_text

    cutoff48 = datetime.now(timezone.utc) - timedelta(hours=48)
    result = await db.execute(
        sa_text("""
            SELECT DISTINCT ON (kw.normalized_kw)
                kw.id, kw.keyword, kw.keyword_ko, kw.kscore, kw.topic,
                kw.country_codes, kw.cluster_ids, kw.event_count,
                kw.severity, kw.is_spike, kw.calculated_at, kw.valid_until,
                COALESCE(ic.independent_sources, 1) AS independent_sources,
                COALESCE(ic.confidence, 0) AS confidence
            FROM trending_keywords kw
            LEFT JOIN issue_clusters ic ON ic.id = (kw.cluster_ids)[1]
            WHERE kw.scope = 'global'
              AND kw.calculated_at >= :cutoff
            ORDER BY kw.normalized_kw, kw.calculated_at DESC
        """),
        {"cutoff": cutoff48},
    )
    rows = result.mappings().all()
    sorted_rows = sorted(rows, key=lambda r: float(r["kscore"]), reverse=True)

    now = datetime.now(timezone.utc)
    return [
        {
            "id": r["id"],
            "keyword": r["keyword"],
            "keyword_ko": r["keyword_ko"],
            "kscore": round(float(r["kscore"]), 2),
            "topic": r["topic"],
            "country_codes": r["country_codes"] or [],
            "event_count": r["event_count"] or 0,
            "severity": r["severity"] or 0,
            "is_spike": bool(r["is_spike"]),
            "independent_sources": int(r["independent_sources"] or 1),
            "confidence": round(float(r["confidence"] or 0), 3),
            "calculated_at": (
                r["calculated_at"].isoformat()
                if hasattr(r["calculated_at"], "isoformat")
                else str(r["calculated_at"])
            ),
            "is_expired": (
                r["valid_until"] < now
                if hasattr(r["valid_until"], "__lt__")
                else False
            ),
        }
        for r in sorted_rows
    ]


@router.post("/trending/recalculate")
async def admin_trending_recalculate(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """트렌딩 수동 재계산."""
    import logging
    _logger = logging.getLogger(__name__)
    from backend.app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as calc_db:
            async with calc_db.begin():
                from worker.processor.trending_engine import calculate_global_trending
                results = await calculate_global_trending(calc_db)
                _logger.info("admin_trending_recalculate 완료: %d개", len(results))
                await _log_action(db, admin, "trending_recalculate", detail={"keywords": len(results)})
                return {"status": "ok", "keywords": len(results)}
    except Exception as e:
        _logger.error("admin_trending_recalculate 실패: %s", e, exc_info=True)
        raise HTTPException(500, detail="트렌딩 재계산 중 오류가 발생했습니다.")


# ── 7일 이벤트 추이 (차트용) ────────────────────────────────────────────────

@router.get("/events/daily-counts")
async def events_daily_counts(
    days: int = Query(7, ge=1, le=30),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """최근 N일 일별 이벤트 수집 수."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            cast(NormalizedEvent.created_at, Date).label("day"),
            func.count().label("count"),
        )
        .where(NormalizedEvent.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    return [{"date": str(row.day), "count": row.count} for row in result.all()]


# ── 푸시 통계 ───────────────────────────────────────────────────────────────

@router.get("/push-stats")
async def push_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_tokens = (await db.execute(
        select(func.count()).select_from(UserPushToken)
    )).scalar() or 0

    # 플랫폼별 분포
    platform_result = await db.execute(
        select(UserPushToken.platform, func.count().label("count"))
        .group_by(UserPushToken.platform)
    )
    platforms = {row.platform: row.count for row in platform_result.all()}

    return {
        "total_tokens": total_tokens,
        "platforms": platforms,
    }


# ── 소스 채널 관리 ─────────────────────────────────────────────────────────

class SourcePatch(BaseModel):
    is_active: Optional[bool] = None
    tier: Optional[str] = None
    base_confidence: Optional[float] = None


@router.get("/sources")
async def list_sources(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """소스 채널 목록 + Redis 수집 상태."""
    import json as _json

    q = select(SourceChannel)
    if source_type:
        q = q.where(SourceChannel.source_type == source_type)
    if tier:
        q = q.where(SourceChannel.tier == tier)
    if is_active is not None:
        q = q.where(SourceChannel.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(SourceChannel.id).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    channels = result.scalars().all()

    # Redis에서 채널별 수집 상태 일괄 조회
    collect_statuses: dict[int, dict] = {}
    try:
        redis = get_redis()
        keys = [f"collect:status:{ch.id}" for ch in channels]
        if keys:
            values = await redis.mget(keys)
            for ch, val in zip(channels, values):
                if val:
                    collect_statuses[ch.id] = _json.loads(val)
    except Exception:
        pass

    return {
        "total": total,
        "items": [
            {
                "id": ch.id,
                "channel_id": ch.channel_id,
                "username": ch.username,
                "display_name": ch.display_name,
                "source_type": ch.source_type,
                "tier": ch.tier,
                "base_confidence": round(ch.base_confidence, 2),
                "language": ch.language,
                "feed_url": ch.feed_url,
                "is_active": ch.is_active,
                "created_at": ch.created_at.isoformat(),
                "collect_status": collect_statuses.get(ch.id),
            }
            for ch in channels
        ],
    }


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: int,
    body: SourcePatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """소스 채널 활성/비활성, 등급, 신뢰도 수정."""
    result = await db.execute(
        select(SourceChannel).where(SourceChannel.id == source_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404)

    changes = {}
    if body.is_active is not None:
        channel.is_active = body.is_active
        changes["is_active"] = body.is_active
    if body.tier is not None:
        if body.tier not in ("A", "B", "C", "D"):
            raise HTTPException(422, detail="tier must be A, B, C, or D")
        channel.tier = body.tier
        changes["tier"] = body.tier
    if body.base_confidence is not None:
        if not (0.0 <= body.base_confidence <= 1.0):
            raise HTTPException(422, detail="base_confidence must be 0.0~1.0")
        channel.base_confidence = body.base_confidence
        changes["base_confidence"] = body.base_confidence

    channel.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await _log_action(db, admin, "update_source", "source_channel", str(source_id), changes)
    return {"status": "ok"}


# ── 피드백 조회 (읽기 전용) ─────────────────────────────────────────────────

@router.get("/feedbacks")
async def list_feedbacks(
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Feedback)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Feedback.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    feedbacks = result.scalars().all()

    user_ids = [f.user_id for f in feedbacks if f.user_id]
    nickname_map: dict[uuid.UUID, str] = {}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.nickname, User.email).where(User.id.in_(user_ids))
        )
        nickname_map = {row.id: (row.nickname or row.email or "익명") for row in user_result.all()}

    return {
        "total": total,
        "items": [
            {
                "id": f.id,
                "user_nickname": nickname_map.get(f.user_id, "익명") if f.user_id else "익명",
                "message": f.message,
                "created_at": f.created_at.isoformat(),
            }
            for f in feedbacks
        ],
    }
