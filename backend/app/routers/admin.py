"""
/admin/* 어드민 전용 API (role=admin만 접근 가능)
"""
from __future__ import annotations
import hmac
import logging
import os
import uuid
from hashlib import sha256
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_, cast, Date, text, delete
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
from backend.app.models.app_event import AppEvent
from backend.app.models.partner import Partner
from backend.app.models.short_link import ShortLink, LinkClick
from backend.app.models.weekly_kpi_snapshot import WeeklyKpiSnapshot
from backend.app.models.social_post import SocialPost, SocialPostPlatform
from backend.app.services.area_activation import sync_area_activation

logger = logging.getLogger(__name__)

# 매출 집계는 한국시간(KST, UTC+9) 기준 "이번달 1일 0시"로 끊는다.
# created_at은 timestamptz라서 타임존 붙은 값으로 비교하면 DB가 알아서 맞춰준다.
KST = timezone(timedelta(hours=9))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bot-stats")
async def bot_stats(
    x_bot_key: Optional[str] = Header(None, alias="X-Bot-Key"),
    db: AsyncSession = Depends(get_db),
):
    """도핑봇 전용 사업지표 — X-Bot-Key 헤더(BOT_STATS_KEY env)로만 접근. 읽기전용 집계만 반환."""
    expected = os.environ.get("BOT_STATS_KEY")
    if not expected or not x_bot_key or not hmac.compare_digest(x_bot_key, expected):
        raise HTTPException(status_code=403, detail="forbidden")
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 이번달 1일 0시를 한국시간 기준으로 잡는다 (UTC로 끊으면 한국 새벽 0~9시 매출이 전달로 빠진다)
    month_start = datetime.now(KST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_users = (await db.execute(select(func.count()).select_from(User).where(User.status != "deleted"))).scalar() or 0
    new_today = (await db.execute(select(func.count()).select_from(User).where(User.created_at >= today_start))).scalar() or 0
    dau = (await db.execute(select(func.count()).select_from(User).where(User.last_active >= today_start))).scalar() or 0
    subscribers = (await db.execute(select(func.count()).select_from(Subscription).where(Subscription.status == "active"))).scalar() or 0
    monthly_revenue = (await db.execute(select(func.coalesce(func.sum(PaymentHistory.amount), 0)).where(PaymentHistory.status == "success", PaymentHistory.created_at >= month_start))).scalar() or 0
    active_clusters = (await db.execute(select(func.count()).select_from(IssueCluster).where(IssueCluster.severity > 0))).scalar() or 0
    events_today = (await db.execute(select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= today_start))).scalar() or 0
    push_tokens = (await db.execute(select(func.count()).select_from(UserPushToken))).scalar() or 0
    feedback_count = (await db.execute(select(func.count()).select_from(Feedback))).scalar() or 0
    out = {
        "total_users": int(total_users), "new_today": int(new_today), "dau": int(dau),
        "subscribers": int(subscribers), "monthly_revenue": int(monthly_revenue),
        "active_clusters": int(active_clusters), "events_today": int(events_today),
        "push_tokens": int(push_tokens), "feedback_count": int(feedback_count),
    }
    # 퍼널 지표 추가 (activation_rate / retention_d1·d7·d30 / conversion_rate / funnel)
    # 계측 집계가 실패해도 기존 지표는 그대로 반환되도록 방어적으로 처리.
    try:
        from backend.app.services.funnel import compute_funnel_metrics
        out.update(await compute_funnel_metrics(db, now))
    except Exception:
        logger.exception("bot-stats funnel metrics 집계 실패")
    return out


@router.get("/bot-feedback")
async def bot_feedback(
    x_bot_key: Optional[str] = Header(None, alias="X-Bot-Key"),
    db: AsyncSession = Depends(get_db),
):
    """도핑봇 전용 — 최근 인앱 피드백(의견 보내기) 메시지. X-Bot-Key 헤더로만. 읽기전용."""
    expected = os.environ.get("BOT_STATS_KEY")
    if not expected or not x_bot_key or not hmac.compare_digest(x_bot_key, expected):
        raise HTTPException(status_code=403, detail="forbidden")
    total = (await db.execute(select(func.count()).select_from(Feedback))).scalar() or 0
    rows = (await db.execute(select(Feedback).order_by(Feedback.created_at.desc()).limit(40))).scalars().all()
    items = [{"message": (r.message or "")[:300], "category": r.category, "status": r.status,
              "at": r.created_at.isoformat() if r.created_at else None} for r in rows]
    return {"total": int(total), "recent": items}


def _send_email(to: str, subject: str, html: str, from_addr: str | None = None):
    """이메일 발송. RESEND_API_KEY 있으면 Resend HTTP API, 없으면 SMTP 폴백."""
    import os
    resend_key = os.environ.get("RESEND_API_KEY")

    if resend_key:
        return _send_via_resend(resend_key, to, subject, html, from_addr)
    else:
        return _send_via_smtp(to, subject, html, from_addr)


def _send_via_resend(api_key: str, to: str, subject: str, html: str, from_addr: str | None = None):
    """Resend HTTP API로 발송 (Railway SMTP 차단 우회)."""
    import json
    import urllib.request

    sender = from_addr or "WeWantPeace <noreply@wewantpeace.live>"
    data = json.dumps({
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "WeWantPeace/1.0",
        },
    )
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    return result


def _send_via_smtp(to: str, subject: str, html: str, from_addr: str | None = None):
    """SMTP 폴백 (로컬 개발용)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from backend.app.core.config import settings

    sender = from_addr or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    smtp.starttls()
    smtp.login(settings.smtp_user, settings.smtp_password)
    smtp.sendmail(sender, to, msg.as_string())
    smtp.quit()


def _send_email_bulk(recipients: list[tuple[str, str, str]], from_addr: str | None = None):
    """여러 수신자에게 발송. [(to, subject, html), ...]"""
    import os
    resend_key = os.environ.get("RESEND_API_KEY")

    sent = 0
    failed = 0
    errors = []

    if resend_key:
        for to, subject, html in recipients:
            try:
                _send_via_resend(resend_key, to, subject, html, from_addr)
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{to}: {e}")
    else:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from backend.app.core.config import settings

        sender = from_addr or settings.smtp_user
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)

        for to, subject, html in recipients:
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = sender
                msg["To"] = to
                msg["Subject"] = subject
                msg.attach(MIMEText(html, "html", "utf-8"))
                smtp.sendmail(sender, to, msg.as_string())
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{to}: {e}")

        try:
            smtp.quit()
        except Exception:
            pass

    return {"sent": sent, "failed": failed, "errors": errors}

ADMIN_SETTINGS_KEY = "admin:settings:v1"


@router.get("/ping")
async def admin_ping(admin: User = Depends(require_admin)):
    """어드민 권한 확인용 경량 엔드포인트 (DB 쿼리 없음)."""
    return {"ok": True}


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

    # 이번달 1일 0시를 한국시간 기준으로 잡는다 (UTC로 끊으면 한국 새벽 0~9시 매출이 전달로 빠진다)
    month_start = datetime.now(KST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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

    # ── 데이터 품질 KPI (최근 24시간) — 단일 쿼리로 통합 ──
    cutoff_24h = now - timedelta(hours=24)

    quality_q = await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE topic = 'unknown') AS unclassified,
            COUNT(*) FILTER (WHERE title_ko IS NULL) AS translation_fail,
            COUNT(*) FILTER (WHERE country_code IS NULL) AS geo_fail
        FROM normalized_events
        WHERE created_at >= :cutoff
    """), {"cutoff": cutoff_24h})
    qr = quality_q.fetchone()
    events_24h = qr[0] or 0
    unclassified_24h = qr[1] or 0
    translation_fail_24h = qr[2] or 0
    geo_fail_24h = qr[3] or 0

    unclassified_rate = round(unclassified_24h / max(1, events_24h) * 100, 1)
    translation_fail_rate = round(translation_fail_24h / max(1, events_24h) * 100, 1)
    geo_fail_rate = round(geo_fail_24h / max(1, events_24h) * 100, 1)

    # ── 주간 비교 (이번 주 vs 지난 주) — 2개 쿼리로 통합 ──
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start

    wc_q1 = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE created_at >= :tw) AS users_this,
            COUNT(*) FILTER (WHERE created_at >= :lw AND created_at < :lwe) AS users_last
        FROM users WHERE created_at >= :lw
    """), {"tw": this_week_start, "lw": last_week_start, "lwe": last_week_end})
    wr1 = wc_q1.fetchone()
    wc_new_users_this = wr1[0] or 0
    wc_new_users_last = wr1[1] or 0

    wc_events_this = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= this_week_start)
    )).scalar() or 0
    wc_events_last = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= last_week_start, NormalizedEvent.created_at < last_week_end)
    )).scalar() or 0

    wc_q2 = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE created_at >= :tw AND status IN ('active','trial')) AS subs_this,
            COUNT(*) FILTER (WHERE created_at >= :lw AND created_at < :lwe AND status IN ('active','trial')) AS subs_last,
            COUNT(*) FILTER (WHERE trial_start >= :tw) AS trials_this,
            COUNT(*) FILTER (WHERE trial_start >= :lw AND trial_start < :lwe) AS trials_last
        FROM subscriptions WHERE (created_at >= :lw OR trial_start >= :lw)
    """), {"tw": this_week_start, "lw": last_week_start, "lwe": last_week_end})
    wr2 = wc_q2.fetchone()
    wc_subs_this = wr2[0] or 0
    wc_subs_last = wr2[1] or 0
    wc_trials_this = wr2[2] or 0
    wc_trials_last = wr2[3] or 0

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
        # 주간 비교
        "week_comparison": {
            "new_users": {"this": wc_new_users_this, "last": wc_new_users_last},
            "events": {"this": wc_events_this, "last": wc_events_last},
            "subscriptions": {"this": wc_subs_this, "last": wc_subs_last},
            "trials": {"this": wc_trials_this, "last": wc_trials_last},
        },
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
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from backend.app.models.app_event import AppEvent

    filters = []
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        filters.append((User.email.ilike(f"%{safe_search}%")) | (User.nickname.ilike(f"%{safe_search}%")))
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

    # visit_count subquery
    visit_sub = (
        select(AppEvent.user_id, func.count().label("visit_count"))
        .where(or_(AppEvent.session_id.is_(None), AppEvent.session_id != "backfill"))
        .group_by(AppEvent.user_id)
        .subquery()
    )

    # active subscription subquery (유저별 최신 1건 — DISTINCT ON)
    # cancelled + expires_at > now도 유효 (결제 기간 남은 취소 구독)
    now = datetime.now(timezone.utc)
    sub_sub = (
        select(Subscription)
        .where(or_(
            Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"]),
            and_(Subscription.status == "cancelled", Subscription.expires_at > now),
        ))
        .distinct(Subscription.user_id)
        .order_by(Subscription.user_id, Subscription.created_at.desc())
        .subquery()
    )

    # paginated rows with visit_count + subscription
    q = (
        select(
            User,
            func.coalesce(visit_sub.c.visit_count, 0).label("visit_count"),
            sub_sub.c.status.label("sub_status"),
            sub_sub.c.billing_key.label("sub_billing_key"),
            sub_sub.c.dodo_subscription_id.label("sub_dodo_id"),
            sub_sub.c.started_at.label("sub_started_at"),
            sub_sub.c.expires_at.label("sub_expires_at"),
            sub_sub.c.trial_start.label("sub_trial_start"),
            sub_sub.c.trial_end.label("sub_trial_end"),
            sub_sub.c.platform.label("sub_platform"),
        )
        .outerjoin(visit_sub, User.id == visit_sub.c.user_id)
        .outerjoin(sub_sub, User.id == sub_sub.c.user_id)
    )
    if filters:
        q = q.where(and_(*filters))

    # sorting
    sort_col_map = {
        "nickname": User.nickname,
        "created_at": User.created_at,
        "last_active": User.last_active,
        "visit_count": func.coalesce(visit_sub.c.visit_count, 0),
        "plan": User.plan,
    }
    sort_col = sort_col_map.get(sort_by, User.created_at)
    q = q.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())
    q = q.offset((page - 1) * limit).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    def _auth_provider(fuid: str) -> str:
        """firebase_uid 패턴으로 로그인 방식 판별."""
        if fuid.startswith("toss:"):
            return "toss"
        if fuid.startswith("apple:") or ".apple." in fuid:
            return "apple"
        return "google"

    def _sub_type(user_obj, s_status, s_billing_key, s_dodo_id, s_platform=None):
        """구독 타입 판별: paid / trial / promo / admin / free"""
        if user_obj.plan == "free":
            return "free"
        if s_status == "trial":
            return "trial"
        if s_status in ("active", "grace_period", "billing_retry", "cancelled"):
            # paid: billing_key(토스) / dodo_subscription_id / platform이 결제 플랫폼
            if s_billing_key or s_dodo_id or s_platform in ("dodopayments", "android", "ios", "web"):
                return "paid"
            return "promo"
        # 구독 없지만 plan != free → 어드민 수동 부여
        if user_obj.admin_plan_override:
            return "admin"
        return "promo"

    return {
        "total": total,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "auth_provider": _auth_provider(u.firebase_uid),
                "nickname": u.nickname,
                "display_name": u.display_name,
                "plan": u.plan,
                "status": u.status,
                "role": u.role,
                "created_at": u.created_at.isoformat(),
                "last_active": u.last_active.isoformat() if u.last_active else None,
                "visit_count": vc,
                "sub_type": _sub_type(u, sub_status, sub_bk, sub_dodo, sub_plat),
                "sub_started_at": sub_started.isoformat() if sub_started else None,
                "sub_expires_at": sub_expires.isoformat() if sub_expires else None,
                "sub_trial_start": sub_ts.isoformat() if sub_ts else None,
                "sub_trial_end": sub_te.isoformat() if sub_te else None,
                "sub_platform": sub_plat,
            }
            for u, vc, sub_status, sub_bk, sub_dodo, sub_started, sub_expires, sub_ts, sub_te, sub_plat in rows
        ],
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, detail="잘못된 사용자 ID 형식입니다.")
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="사용자를 찾을 수 없습니다.")
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
        "last_active": user.last_active.isoformat() if user.last_active else None,
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
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, detail="잘못된 사용자 ID 형식입니다.")
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="사용자를 찾을 수 없습니다.")

    changes = {}
    if body.plan is not None:
        user.plan = body.plan
        changes["plan"] = body.plan
        # 어드민 수동 플랜 설정 플래그 (expire_subscriptions 다운그레이드 방지)
        user.admin_plan_override = body.plan != "free"
        # 플랜 변경 시 관심국가 활성화 동기화
        await sync_area_activation(user.id, body.plan, db)
        # 어드민이 free로 변경 시 활성 구독도 취소 (웹훅이 플랜 복원하는 버그 방지)
        if body.plan == "free":
            active_subs = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"]),
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
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, detail="잘못된 사용자 ID 형식입니다.")
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="사용자를 찾을 수 없습니다.")
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
        except Exception as e:
            logger.debug("admin: %s", e)

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
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        filters.append(Post.title.ilike(f"%{safe_search}%"))
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
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """유료 플랜 사용자 목록 (결제 구독 + 어드민 부여 모두 포함)."""
    from sqlalchemy.orm import aliased
    Sub = aliased(Subscription)

    # users.plan != 'free' 인 유저 조회, 최신 구독 정보 LEFT JOIN
    # cancelled + expires_at > now도 유효한 구독
    now_sub = datetime.now(timezone.utc)
    q = (
        select(User, Subscription)
        .outerjoin(
            Subscription,
            (Subscription.user_id == User.id) & (
                (Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"])) |
                ((Subscription.status == "cancelled") & (Subscription.expires_at > now_sub))
            ),
        )
        .where(User.plan != "free")
    )
    if plan:
        q = q.where(User.plan == plan)

    total = (await db.execute(
        select(func.count()).select_from(
            select(User.id).where(User.plan != "free")
            .where(User.plan == plan if plan else True)
            .subquery()
        )
    )).scalar() or 0

    q = q.order_by(User.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    rows = result.all()
    return {
        "total": total,
        "items": [
            {
                "id": str(u.id),
                "user_id": str(u.id),
                "email": u.email,
                "nickname": u.nickname,
                "plan": u.plan,
                "status": s.status if s else "admin_granted",
                "amount": s.amount if s else 0,
                "currency": s.currency if s else "USD",
                "platform": s.platform if s else "admin",
                "started_at": (s.started_at.isoformat() if s else u.created_at.isoformat()),
                "expires_at": (s.expires_at.isoformat() if s and s.expires_at else None),
                "next_billing_at": (s.next_billing_at.isoformat() if s and s.next_billing_at else None),
                "created_at": u.created_at.isoformat(),
            }
            for u, s in rows
        ],
    }


# ── 앱 설정 ──────────────────────────────────────────────────────────────────

class AppSettings(BaseModel):
    maintenance_mode: bool = False
    allow_signup: bool = True
    pro_price: int = 699
    pro_plus_price: int = 999
    notice_banner: str = ""


@router.get("/settings")
async def get_settings(admin: User = Depends(require_admin)):
    import json
    try:
        redis = get_redis()
        cached = await redis.get(ADMIN_SETTINGS_KEY)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug("admin: %s", e)
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
    except Exception as e:
        logger.debug("admin: %s", e)
    await _log_action(db, admin, "update_settings", detail=body.dict())
    return body


# ── 클러스터 관리 ───────────────────────────────────────────────────────────

class ClusterPatch(BaseModel):
    severity: Optional[int] = None
    topic: Optional[str] = None
    is_active: Optional[bool] = None
    title: Optional[str] = None
    title_ko: Optional[str] = None


@router.get("/clusters")
async def list_clusters(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    severity: Optional[int] = Query(None),
    topic: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    flagged: Optional[bool] = Query(None),
    active: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(IssueCluster)
    if flagged is not None:
        q = q.where(IssueCluster.is_flagged == flagged)
    if active is not None:
        q = q.where(IssueCluster.is_active == active)
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        q = q.where(
            (IssueCluster.title.ilike(f"%{safe_search}%"))
            | (IssueCluster.title_ko.ilike(f"%{safe_search}%"))
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
                "is_spike": False,  # v7: deprecated
                "is_active": c.is_active,
                "is_flagged": c.is_flagged,
                "first_event_at": c.first_event_at.isoformat(),
                "last_event_at": c.last_event_at.isoformat(),
                "created_at": c.created_at.isoformat(),
            }
            for c in clusters
        ],
    }


@router.get("/spike-clusters")
async def list_spike_clusters(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """v7: 고KScore 클러스터 목록 (KScore >= 5.0, severity>0). 기존 spike-clusters 경로 유지."""
    q = (
        select(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.kscore >= 5.0)
        .order_by(IssueCluster.kscore.desc())
        .limit(20)
    )
    result = await db.execute(q)
    clusters = result.scalars().all()
    return {
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
                "is_spike": False,  # v7: deprecated
                "is_active": c.is_active,
                "first_event_at": c.first_event_at.isoformat(),
                "last_event_at": c.last_event_at.isoformat(),
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

    from backend.app.models.cluster_change_log import ClusterChangeLog

    changes = {}
    change_logs = []

    if body.severity is not None and cluster.severity != body.severity:
        change_logs.append(ClusterChangeLog(
            cluster_id=cluster.id, field="severity",
            old_value=str(cluster.severity), new_value=str(body.severity),
            reason="admin_edit", updated_by=admin.email or "admin",
        ))
        cluster.severity = body.severity
        changes["severity"] = body.severity
    if body.topic is not None and cluster.topic != body.topic:
        change_logs.append(ClusterChangeLog(
            cluster_id=cluster.id, field="topic",
            old_value=cluster.topic, new_value=body.topic,
            reason="admin_edit", updated_by=admin.email or "admin",
        ))
        cluster.topic = body.topic
        changes["topic"] = body.topic
    if body.is_active is not None:
        # is_active → severity 0 으로 비활성화
        if not body.is_active:
            cluster.severity = 0
            changes["deactivated"] = True
        changes["is_active"] = body.is_active

    # 제목 수정 (title_ko만 전달되면 ko→en 자동 번역)
    if body.title_ko is not None and cluster.title_ko != body.title_ko:
        change_logs.append(ClusterChangeLog(
            cluster_id=cluster.id, field="title_ko",
            old_value=cluster.title_ko, new_value=body.title_ko,
            reason="admin_edit", updated_by=admin.email or "admin",
        ))
        cluster.title_ko = body.title_ko
        changes["title_ko"] = body.title_ko
        if body.title is None:
            try:
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source="ko", target="en").translate(body.title_ko[:200])
                if translated:
                    cluster.title = translated[:200]
                    changes["title"] = cluster.title
            except Exception as e:
                logger.debug("admin: %s", e)
    if body.title is not None and cluster.title != body.title:
        change_logs.append(ClusterChangeLog(
            cluster_id=cluster.id, field="title",
            old_value=cluster.title, new_value=body.title,
            reason="admin_edit", updated_by=admin.email or "admin",
        ))
        cluster.title = body.title
        changes["title"] = body.title

    if change_logs:
        db.add_all(change_logs)

    await db.flush()

    # 제목 변경 시 trending_keywords 행도 동기화 + Redis 캐시 무효화
    if "title" in changes or "title_ko" in changes:
        await db.execute(
            text("""
                UPDATE trending_keywords
                SET keyword = :title, keyword_ko = :title_ko
                WHERE :cid = ANY(cluster_ids)
            """),
            {"title": cluster.title, "title_ko": cluster.title_ko, "cid": uuid.UUID(cluster_id)},
        )
        await db.flush()
        try:
            redis = get_redis()
            await redis.delete("trending:global:v1")
        except Exception as e:
            logger.debug("admin: %s", e)

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
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        q = q.where(
            (NormalizedEvent.title.ilike(f"%{safe_search}%"))
            | (NormalizedEvent.title_ko.ilike(f"%{safe_search}%"))
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


# ── 테스트 푸시 ──────────────────────────────────────────────────────────────

class TestPushRequest(BaseModel):
    title: str = "🔔 WeWantPeace 테스트"
    body: str = "푸시 알림이 정상적으로 도착했습니다!"


@router.post("/test-push")
async def test_push(
    payload: TestPushRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """관리자 본인에게만 테스트 푸시 발송."""
    result = await db.execute(
        select(UserPushToken).where(UserPushToken.user_id == admin.id)
    )
    tokens = result.scalars().all()
    if not tokens:
        raise HTTPException(status_code=404, detail="등록된 FCM 토큰이 없습니다.")

    sent = 0
    errors = []
    invalid_token_ids = []
    try:
        import firebase_admin.messaging as messaging

        for token_obj in tokens:
            try:
                if token_obj.platform in ("android", "ios"):
                    msg = messaging.Message(
                        token=token_obj.fcm_token,
                        notification=messaging.Notification(
                            title=payload.title,
                            body=payload.body,
                        ),
                        data={"type": "test", "admin": "true"},
                        android=messaging.AndroidConfig(
                            priority="high",
                            notification=messaging.AndroidNotification(
                                channel_id="wwp_alerts",
                                priority="high",
                            ),
                        ),
                    )
                else:
                    msg = messaging.Message(
                        token=token_obj.fcm_token,
                        data={
                            "title": payload.title,
                            "body": payload.body,
                            "type": "test",
                        },
                        webpush=messaging.WebpushConfig(headers={"Urgency": "high"}),
                    )
                messaging.send(msg)
                sent += 1
            except Exception as e:
                err_class = type(e).__name__
                errors.append(f"{token_obj.platform}: {str(e)[:100]}")
                # 만료/무효 토큰 자동 정리
                if err_class in ("UnregisteredError", "InvalidArgumentError", "SenderIdMismatchError", "NotFoundError"):
                    invalid_token_ids.append(token_obj.id)
    except ImportError:
        raise HTTPException(status_code=500, detail="firebase_admin 미설치")

    # 무효 토큰 DB에서 삭제
    cleaned = 0
    if invalid_token_ids:
        await db.execute(
            delete(UserPushToken).where(UserPushToken.id.in_(invalid_token_ids))
        )
        await db.commit()
        cleaned = len(invalid_token_ids)

    return {
        "sent": sent,
        "total_tokens": len(tokens),
        "errors": errors,
        "cleaned_tokens": cleaned,
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

    # 전체 활성/비활성 카운트 (필터 무관)
    _counts = await db.execute(
        select(SourceChannel.is_active, func.count())
        .group_by(SourceChannel.is_active)
    )
    _count_map = {row[0]: row[1] for row in _counts.fetchall()}
    active_count = _count_map.get(True, 0)
    inactive_count = _count_map.get(False, 0)

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
    except Exception as e:
        logger.debug("admin: %s", e)

    return {
        "total": total,
        "active_count": active_count,
        "inactive_count": inactive_count,
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
                "api_endpoint": ch.api_endpoint,
                "topics": ch.topics or [],
                "geo_focus": ch.geo_focus or [],
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


# ── 이벤트 재처리 (severity 재계산 + 클러스터 병합) ──────────────────────────

@router.post("/reprocess-events")
async def reprocess_events(
    country: Optional[str] = Query(None, description="국가 코드 (예: IR). 미지정 시 최근 24h 전체"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    severity 키워드 변경 후 기존 이벤트의 severity 재계산.
    분산된 고심각도 클러스터를 하나로 병합.
    """
    import logging
    _logger = logging.getLogger(__name__)
    from worker.processor.normalizer import _classify_topic, _calculate_severity
    from worker.processor.trending_engine import _calc_kscore

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        # 1) normalized_events severity 재계산
        q = select(NormalizedEvent).where(NormalizedEvent.created_at >= cutoff)
        if country:
            q = q.where(NormalizedEvent.country_code == country.upper())
        result = await db.execute(q)
        events = result.scalars().all()

        sev_updated = 0
        for ev in events:
            text = f"{ev.title or ''} {ev.body or ''}"
            new_topic = _classify_topic(text)
            new_sev = _calculate_severity(text, new_topic)
            if new_sev != ev.severity or new_topic != ev.topic:
                ev.severity = new_sev
                ev.topic = new_topic
                sev_updated += 1

        await db.flush()

        # 2) 분산 클러스터 병합: 같은 country+topic에서 severity>=50인 것들을 하나로
        cq = select(IssueCluster).where(
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.severity >= 50,
        )
        if country:
            cq = cq.where(IssueCluster.country_code == country.upper())
        cq = cq.order_by(IssueCluster.country_code, IssueCluster.topic, IssueCluster.kscore.desc())
        cresult = await db.execute(cq)
        clusters = cresult.scalars().all()

        # country+topic 별로 그룹핑
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)
        for c in clusters:
            if c.country_code and c.topic in ("conflict", "terror", "coup"):
                groups[f"{c.country_code}:{c.topic}"].append(c)

        merged_count = 0
        for key, group in groups.items():
            if len(group) <= 1:
                continue
            # kscore 최고인 것을 winner로, 나머지 흡수
            winner = group[0]
            for loser in group[1:]:
                winner.event_count += loser.event_count
                winner.independent_sources = (winner.independent_sources or 1) + (loser.independent_sources or 1)
                if loser.severity > winner.severity:
                    winner.severity = loser.severity
                winner.confidence = round(
                    max(winner.confidence, loser.confidence), 3
                )
                # source_tiers 병합
                existing = list(winner.source_tiers or [])
                existing.extend(loser.source_tiers or [])
                winner.source_tiers = existing
                # 시간 범위 확장
                if loser.first_event_at < winner.first_event_at:
                    winner.first_event_at = loser.first_event_at
                if loser.last_event_at > winner.last_event_at:
                    winner.last_event_at = loser.last_event_at
                    winner.window_end = loser.last_event_at + timedelta(minutes=60)
                # cluster_events 재할당
                from backend.app.models.issue_cluster import ClusterEvent
                await db.execute(
                    text("UPDATE cluster_events SET cluster_id = :winner WHERE cluster_id = :loser"),
                    {"winner": winner.id, "loser": loser.id},
                )
                # loser 비활성화 (severity=0)
                loser.severity = 0
                loser.kscore = 0
                merged_count += 1

            # winner kscore 재계산
            winner.kscore, _ = _calc_kscore(
                event_count=winner.event_count,
                is_spike=winner.is_spike,
                confidence=winner.confidence,
                severity=winner.severity,
                independent_sources=winner.independent_sources or 1,
                source_tiers=winner.source_tiers or [],
            )
            winner.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await _log_action(db, admin, "reprocess_events", detail={
            "country": country,
            "severity_updated": sev_updated,
            "clusters_merged": merged_count,
        })

        # 3) 트렌딩 재계산
        from backend.app.core.database import AsyncSessionLocal
        trending_count = 0
        try:
            async with AsyncSessionLocal() as calc_db:
                async with calc_db.begin():
                    from worker.processor.trending_engine import calculate_global_trending
                    results = await calculate_global_trending(calc_db)
                    trending_count = len(results)
        except Exception as e:
            _logger.warning("트렌딩 재계산 실패: %s", e)

        return {
            "status": "ok",
            "severity_updated": sev_updated,
            "clusters_merged": merged_count,
            "trending_recalculated": trending_count,
        }
    except Exception as e:
        _logger.error("reprocess_events 실패: %s", e, exc_info=True)
        raise HTTPException(500, detail=f"재처리 실패: {str(e)}")


# ── 피드백 조회 (읽기 전용) ─────────────────────────────────────────────────

@router.get("/feedbacks")
async def list_feedbacks(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Feedback)
    filters = []
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        filters.append(Feedback.message.ilike(f"%{safe_search}%"))
    if date_from:
        filters.append(Feedback.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Feedback.created_at <= datetime.fromisoformat(date_to))
    if filters:
        q = q.where(and_(*filters))
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


# ── 클러스터 쓰레기 제목 일괄 수정 ──────────────────────────────────────────

import re as _re


def _is_junk(title: str) -> bool:
    stripped = _re.sub(r'#\w+', '', title).strip()
    return len(stripped) < 5


def _translate(title: str) -> str | None:
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source="en", target="ko").translate(title[:200])
        return result[:70] if result else None
    except Exception:
        return None


@router.post("/fix-junk-titles")
async def fix_junk_titles(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """해시태그만 있는 쓰레기 제목을 가진 클러스터를 같은 토픽/국가 이벤트에서 찾은 좋은 제목으로 교체."""
    result = await db.execute(
        select(IssueCluster)
        .where(IssueCluster.severity > 0)
        .order_by(IssueCluster.last_event_at.desc())
    )
    clusters = result.scalars().all()

    fixed = []
    for c in clusters:
        if not _is_junk(c.title):
            continue

        # 같은 토픽+국가+시간범위에서 좋은 제목 찾기
        ev_result = await db.execute(
            text("""
                SELECT title FROM normalized_events
                WHERE topic = :topic
                  AND (:cc IS NULL OR country_code = :cc)
                  AND event_time BETWEEN :ws AND :we
                ORDER BY severity DESC, confidence DESC
                LIMIT 20
            """),
            {"topic": c.topic, "cc": c.country_code,
             "ws": c.window_start, "we": c.window_end},
        )
        events = ev_result.fetchall()

        best = None
        for ev in events:
            if not _is_junk(ev[0]) and len(ev[0]) > len(best or ""):
                best = ev[0]

        if not best:
            continue

        old_title = c.title
        c.title = best
        c.title_ko = _translate(best)
        fixed.append({"id": str(c.id), "old": old_title, "new": best, "ko": c.title_ko})

    await db.commit()
    await _log_action(db, admin, "fix_junk_titles", detail={"count": len(fixed)})
    return {"fixed": len(fixed), "details": fixed}


# ── 댓글 관리 ─────────────────────────────────────────────────────────────────

from backend.app.models.community import Comment

@router.get("/comments")
async def list_admin_comments(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Comment)
    if status:
        q = q.where(Comment.status == status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Comment.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    comments = result.scalars().all()

    # author + post title 조회
    user_ids = list({c.user_id for c in comments if c.user_id})
    post_ids = list({c.post_id for c in comments if c.post_id})

    nickname_map: dict[uuid.UUID, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname).where(User.id.in_(user_ids)))
        nickname_map = {row.id: row.nickname for row in ur.all()}

    post_title_map: dict[uuid.UUID, str] = {}
    if post_ids:
        pr = await db.execute(select(Post.id, Post.title).where(Post.id.in_(post_ids)))
        post_title_map = {row.id: row.title for row in pr.all()}

    return {
        "total": total,
        "items": [
            {
                "id": str(c.id),
                "post_id": str(c.post_id),
                "post_title": post_title_map.get(c.post_id, ""),
                "content": c.content,
                "author_nickname": nickname_map.get(c.user_id) if c.user_id else None,
                "status": c.status,
                "like_count": c.like_count,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments
        ],
    }


@router.patch("/comments/{comment_id}/hide")
async def hide_comment(
    comment_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Comment).where(Comment.id == uuid.UUID(comment_id)))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404)
    comment.status = "hidden" if comment.status == "active" else "active"
    await db.flush()
    await _log_action(db, admin, "hide_comment", "comment", comment_id, {"new_status": comment.status})
    return {"status": comment.status}


# ── 어드민 로그 조회 ──────────────────────────────────────────────────────────

@router.get("/logs")
async def list_admin_logs(
    page: int = Query(1, ge=1),
    action: Optional[str] = Query(None),
    admin_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AdminLog)
    filters = []
    if action:
        filters.append(AdminLog.action == action)
    if admin_id:
        filters.append(AdminLog.admin_id == uuid.UUID(admin_id))
    if date_from:
        filters.append(AdminLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(AdminLog.created_at <= datetime.fromisoformat(date_to))
    if filters:
        q = q.where(and_(*filters))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(AdminLog.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    logs = result.scalars().all()

    admin_ids = list({l.admin_id for l in logs if l.admin_id})
    nickname_map: dict[uuid.UUID, str] = {}
    if admin_ids:
        ur = await db.execute(select(User.id, User.nickname).where(User.id.in_(admin_ids)))
        nickname_map = {row.id: row.nickname for row in ur.all()}

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "admin_nickname": nickname_map.get(l.admin_id) if l.admin_id else None,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "detail": l.detail,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }


# ── 마케팅 동의 관리 ──────────────────────────────────────────────────────────

from backend.app.models.community import MarketingEmailLog

@router.get("/marketing")
async def list_marketing_users(
    page: int = Query(1, ge=1),
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).where(User.marketing_agreed_at != None, User.status != "deleted")
    if plan:
        q = q.where(User.plan == plan)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(User.marketing_agreed_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    users = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "nickname": u.nickname,
                "plan": u.plan,
                "marketing_agreed_at": u.marketing_agreed_at.isoformat() if u.marketing_agreed_at else None,
            }
            for u in users
        ],
    }


@router.get("/marketing/export-csv")
async def export_marketing_csv(
    plan: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import StreamingResponse
    import io, csv

    q = select(User.email, User.nickname, User.plan).where(
        User.marketing_agreed_at != None, User.status != "deleted", User.email != None
    )
    if plan:
        q = q.where(User.plan == plan)
    result = await db.execute(q)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "nickname", "plan"])
    for row in rows:
        writer.writerow([row.email, row.nickname or "", row.plan])

    await _log_action(db, admin, "export_marketing_csv", detail={"count": len(rows)})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=marketing_users.csv"},
    )


class SendEmailBody(BaseModel):
    subject: str
    body: str
    plan_filter: Optional[str] = None


@router.post("/marketing/send-email")
async def send_marketing_email(
    body: SendEmailBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """마케팅 이메일 발송."""
    # 대상 유저 조회
    q = select(User.email).where(
        User.marketing_agreed_at != None, User.status != "deleted", User.email != None
    )
    if body.plan_filter:
        q = q.where(User.plan == body.plan_filter)
    result = await db.execute(q)
    emails = [row.email for row in result.all() if row.email]

    if not emails:
        raise HTTPException(400, detail="발송 대상이 없습니다.")

    # 로그 생성
    log = MarketingEmailLog(
        admin_id=admin.id,
        subject=body.subject,
        body=body.body,
        sent_count=0,
        failed_count=0,
        status="sending",
    )
    db.add(log)
    await db.flush()

    # 발송
    try:
        recipients = [(email, body.subject, body.body) for email in emails]
        result = _send_email_bulk(recipients)
        sent = result["sent"]
        failed = result["failed"]
    except Exception as e:
        log.status = "failed"
        log.failed_count = len(emails)
        await db.flush()
        raise HTTPException(500, detail=f"이메일 발송 실패: {str(e)}")

    log.sent_count = sent
    log.failed_count = failed
    log.status = "completed"
    await db.flush()
    await _log_action(db, admin, "send_marketing_email", detail={"sent": sent, "failed": failed})

    return {"status": "ok", "sent": sent, "failed": failed}


@router.get("/marketing/email-logs")
async def list_email_logs(
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(MarketingEmailLog)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(MarketingEmailLog.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    logs = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "subject": l.subject,
                "sent_count": l.sent_count,
                "failed_count": l.failed_count,
                "status": l.status,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }


# ── 파이프라인 통합 통계 ──────────────────────────────────────────────────────

@router.get("/pipeline/stats")
async def pipeline_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 파이프라인 단계별 통계를 한 번에 반환."""
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # 1) 소스 통계
    total_sources = (await db.execute(
        select(func.count()).select_from(SourceChannel)
    )).scalar() or 0
    active_sources = (await db.execute(
        select(func.count()).select_from(SourceChannel).where(SourceChannel.is_active == True)
    )).scalar() or 0

    # 오류 소스: Redis collect:status:{id} 조회
    error_sources = 0
    try:
        import json as _json
        redis = get_redis()
        all_src = await db.execute(
            select(SourceChannel.id).where(SourceChannel.is_active == True)
        )
        src_ids = [r[0] for r in all_src.all()]
        if src_ids:
            keys = [f"collect:status:{sid}" for sid in src_ids]
            vals = await redis.mget(keys)
            for val in vals:
                if val:
                    st = _json.loads(val)
                    if st.get("status") == "error":
                        error_sources += 1
    except Exception as e:
        logger.debug("admin: %s", e)

    # RSS / Telegram 비율
    rss_count = (await db.execute(
        select(func.count()).select_from(SourceChannel)
        .where(SourceChannel.is_active == True, SourceChannel.source_type == "rss")
    )).scalar() or 0
    telegram_count = (await db.execute(
        select(func.count()).select_from(SourceChannel)
        .where(SourceChannel.is_active == True, SourceChannel.source_type == "telegram")
    )).scalar() or 0

    # 2) 정규화 이벤트 통계
    events_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h)
    )).scalar() or 0

    unclassified_24h = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.topic == "unknown")
    )).scalar() or 0

    translation_fail = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.title_ko == None)
    )).scalar() or 0

    geo_fail = (await db.execute(
        select(func.count()).select_from(NormalizedEvent)
        .where(NormalizedEvent.created_at >= cutoff_24h, NormalizedEvent.country_code == None)
    )).scalar() or 0

    unclassified_rate = round(unclassified_24h / max(1, events_24h), 3)
    translation_fail_rate = round(translation_fail / max(1, events_24h), 3)
    geo_fail_rate = round(geo_fail / max(1, events_24h), 3)

    # 3) 토픽 분포
    topic_rows = await db.execute(
        select(NormalizedEvent.topic, func.count().label("count"))
        .where(NormalizedEvent.created_at >= cutoff_24h)
        .group_by(NormalizedEvent.topic)
        .order_by(func.count().desc())
    )
    topic_distribution = [
        {"topic": row.topic or "unknown", "count": row.count}
        for row in topic_rows.all()
    ]

    # 4) 중복 제거 (RawEvent 대비)
    raw_24h = (await db.execute(
        select(func.count()).select_from(RawEvent)
        .where(RawEvent.collected_at >= cutoff_24h)
    )).scalar() or 0
    duplicates_24h = max(0, raw_24h - events_24h)

    # 5) 클러스터 통계
    active_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.severity > 0)
    )).scalar() or 0
    noise_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.severity == 0)
    )).scalar() or 0
    # v7: spike_clusters → high_kscore_clusters (KScore >= 5.0)
    spike_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.kscore >= 5.0)
    )).scalar() or 0

    # 6) 푸시 토큰 통계
    push_tokens = (await db.execute(
        select(func.count()).select_from(UserPushToken)
    )).scalar() or 0
    platform_rows = await db.execute(
        select(UserPushToken.platform, func.count().label("count"))
        .group_by(UserPushToken.platform)
    )
    platform_map = {r.platform: r.count for r in platform_rows.all()}
    push_web = platform_map.get("web", 0)
    push_android = platform_map.get("android", 0)
    push_ios = platform_map.get("ios", 0)

    # 7) 위기 국가
    crisis_q = await db.execute(
        select(TensionIndex.country_code)
        .where(TensionIndex.tension_level == 3)
        .group_by(TensionIndex.country_code)
    )
    crisis_countries = len(crisis_q.all())

    # ── alert delivery 통계 (최근 6시간) ──
    alert_sent_6h = 0
    alert_failed_6h = 0
    alert_pending = 0
    alert_suppressed_6h = 0
    try:
        _q = await db.execute(text(
            "SELECT decision, COUNT(*) as cnt FROM alert_delivery_log"
            " WHERE created_at >= NOW() - INTERVAL '6 hours'"
            " GROUP BY decision"
        ))
        for row in _q.fetchall():
            if row.decision == 'sent': alert_sent_6h = row.cnt
            elif row.decision == 'failed': alert_failed_6h = row.cnt
            elif row.decision == 'pending': alert_pending += row.cnt
            elif row.decision == 'suppressed': alert_suppressed_6h = row.cnt
    except Exception as e:
        logger.debug("admin: %s", e)

    # pending은 전체 시간에서
    try:
        _q2 = await db.execute(text("SELECT COUNT(*) FROM alert_delivery_log WHERE decision = 'pending'"))
        alert_pending = _q2.scalar() or 0
    except Exception as e:
        logger.debug("admin: %s", e)

    # ── spike delivery 통계 (최근 6시간) ──
    spike_total_6h = 0
    spike_delivered_6h = 0
    spike_undelivered_6h = 0
    try:
        _q3 = await db.execute(text(
            "SELECT COUNT(*) FROM spike_events WHERE triggered_at >= NOW() - INTERVAL '6 hours'"
        ))
        spike_total_6h = _q3.scalar() or 0

        _q4 = await db.execute(text("""
            SELECT COUNT(DISTINCT se.id) FROM spike_events se
            JOIN alert_delivery_log adl ON adl.spike_event_id = se.id
            WHERE se.triggered_at >= NOW() - INTERVAL '6 hours'
              AND adl.decision = 'sent'
        """))
        spike_delivered_6h = _q4.scalar() or 0
        spike_undelivered_6h = spike_total_6h - spike_delivered_6h
    except Exception as e:
        logger.debug("admin: %s", e)

    # ── SNS 소셜 포스트 통계 ──
    sns_pending_review = 0
    sns_approved = 0
    sns_published_24h = 0
    sns_failed_24h = 0
    try:
        _q5 = await db.execute(text(
            "SELECT status, COUNT(*) as cnt FROM social_posts"
            " WHERE status IN ('pending_review', 'approved', 'published', 'failed')"
            " GROUP BY status"
        ))
        for row in _q5.fetchall():
            if row.status == 'pending_review': sns_pending_review = row.cnt
            elif row.status == 'approved': sns_approved = row.cnt

        _q6 = await db.execute(text(
            "SELECT status, COUNT(*) as cnt FROM social_posts"
            " WHERE created_at >= NOW() - INTERVAL '24 hours'"
            " AND status IN ('published', 'failed')"
            " GROUP BY status"
        ))
        for row in _q6.fetchall():
            if row.status == 'published': sns_published_24h = row.cnt
            elif row.status == 'failed': sns_failed_24h = row.cnt
    except Exception as e:
        logger.debug("admin: %s", e)

    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "error_sources": error_sources,
        "rss_count": rss_count,
        "telegram_count": telegram_count,
        "events_24h": events_24h,
        "unclassified_rate": unclassified_rate,
        "translation_fail_rate": translation_fail_rate,
        "geo_fail_rate": geo_fail_rate,
        "topic_distribution": topic_distribution,
        "raw_24h": raw_24h,
        "duplicates_24h": duplicates_24h,
        "active_clusters": active_clusters,
        "noise_clusters": noise_clusters,
        "spike_clusters": spike_clusters,
        "push_tokens": push_tokens,
        "push_web": push_web,
        "push_android": push_android,
        "push_ios": push_ios,
        "crisis_countries": crisis_countries,
        "alert_sent_6h": alert_sent_6h,
        "alert_failed_6h": alert_failed_6h,
        "alert_pending": alert_pending,
        "alert_suppressed_6h": alert_suppressed_6h,
        "spike_total_6h": spike_total_6h,
        "spike_delivered_6h": spike_delivered_6h,
        "spike_undelivered_6h": spike_undelivered_6h,
        "sns_pending_review": sns_pending_review,
        "sns_approved": sns_approved,
        "sns_published_24h": sns_published_24h,
        "sns_failed_24h": sns_failed_24h,
    }


# ── 오펀 이벤트 재처리 (클러스터 미배정 이벤트) ───────────────────────────────

@router.post("/trigger-orphan-reprocess")
async def trigger_orphan_reprocess(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """클러스터에 배정되지 않은 최근 이벤트를 재처리."""
    import logging
    _logger = logging.getLogger(__name__)

    try:
        from backend.app.models.issue_cluster import ClusterEvent
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        # 클러스터에 속하지 않은 이벤트 수
        orphan_q = (
            select(func.count())
            .select_from(NormalizedEvent)
            .where(
                NormalizedEvent.created_at >= cutoff,
                NormalizedEvent.id.notin_(
                    select(ClusterEvent.event_id)
                ),
            )
        )
        orphan_count = (await db.execute(orphan_q)).scalar() or 0

        # 재처리: severity 재계산
        reprocessed = 0
        if orphan_count > 0:
            from worker.processor.normalizer import _classify_topic, _calculate_severity

            orphans = await db.execute(
                select(NormalizedEvent)
                .where(
                    NormalizedEvent.created_at >= cutoff,
                    NormalizedEvent.id.notin_(select(ClusterEvent.event_id)),
                )
                .limit(500)
            )
            for ev in orphans.scalars().all():
                txt = f"{ev.title or ''} {ev.body or ''}"
                new_topic = _classify_topic(txt)
                new_sev = _calculate_severity(txt, new_topic)
                if new_topic != ev.topic or new_sev != ev.severity:
                    ev.topic = new_topic
                    ev.severity = new_sev
                    reprocessed += 1
            await db.flush()

        await _log_action(db, admin, "trigger_orphan_reprocess", detail={
            "orphan_count": orphan_count,
            "reprocessed": reprocessed,
        })

        return {
            "status": "ok",
            "orphan_count": orphan_count,
            "reprocessed": reprocessed,
        }
    except Exception as e:
        _logger.error("orphan_reprocess 실패: %s", e, exc_info=True)
        raise HTTPException(500, detail=f"오펀 재처리 실패: {str(e)}")


# ── 미처리 raw_events 재처리 트리거 ──────────────────────────────────────────

@router.post("/retry-raw-events")
async def retry_raw_events(
    limit: int = Query(default=200, ge=1, le=1000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """processed=false인 raw_events를 Celery 큐에 다시 넣는다."""
    from worker.tasks import process_raw_event

    result = await db.execute(
        text("SELECT id FROM raw_events WHERE processed = false ORDER BY collected_at ASC LIMIT :lim"),
        {"lim": limit},
    )
    ids = [str(row[0]) for row in result.fetchall()]

    for raw_id in ids:
        process_raw_event.delay(raw_id)

    await _log_action(db, admin, "retry_raw_events", detail={
        "count": len(ids),
    })

    return {"status": "ok", "dispatched": len(ids)}


# ── KPI 대시보드 ──────────────────────────────────────────────────────────────

@router.get("/kpi")
async def get_kpi(
    days: int = Query(default=7, ge=1, le=90),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase Gate KPI 지표: 온보딩율, Paywall 전환율, Trial→Paid, D7 리텐션."""
    from backend.app.models.paywall_event import PaywallEvent

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # ── app_events 집계 ──
    ae_counts_q = await db.execute(
        select(AppEvent.name, func.count())
        .where(AppEvent.created_at >= cutoff)
        .group_by(AppEvent.name)
    )
    ae_counts = {row[0]: row[1] for row in ae_counts_q.all()}

    auth_success = ae_counts.get("auth_success", 0)
    onboarding_complete = ae_counts.get("onboarding_complete", 0)

    # A1: 온보딩 완료율 = onboarding_complete / auth_success
    a1_rate = round(onboarding_complete / max(1, auth_success) * 100, 1)

    # ── Paywall 전환율 ──
    pw_shown = (await db.execute(
        select(func.count()).select_from(PaywallEvent)
        .where(PaywallEvent.action == "shown", PaywallEvent.created_at >= cutoff)
    )).scalar() or 0

    pw_purchase = (await db.execute(
        select(func.count()).select_from(PaywallEvent)
        .where(PaywallEvent.action == "purchase_success", PaywallEvent.created_at >= cutoff)
    )).scalar() or 0

    paywall_rate = round(pw_purchase / max(1, pw_shown) * 100, 1)

    # ── Trial → Paid ──
    from backend.app.models.subscription import Subscription

    trial_started = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(Subscription.trial_start != None, Subscription.trial_start >= cutoff)
    )).scalar() or 0

    trial_converted = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(
            Subscription.trial_start != None,
            Subscription.trial_start >= cutoff,
            Subscription.status == "active",
            Subscription.trial_end != None,
        )
    )).scalar() or 0

    trial_to_paid = round(trial_converted / max(1, trial_started) * 100, 1)

    # ── Promo 전환 ──
    promo_started = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(Subscription.platform.like("promo:%"), Subscription.started_at >= cutoff)
    )).scalar() or 0

    promo_converted = (await db.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.platform.like("promo:%"),
            Subscription.started_at >= cutoff,
        ).where(
            Subscription.user_id.in_(
                select(Subscription.user_id).where(
                    Subscription.platform == "dodopayments",
                    Subscription.status == "active",
                )
            )
        )
    )).scalar() or 0

    promo_to_paid = round(promo_converted / max(1, promo_started) * 100, 1)

    # ── Trial 만료 후 7일내 할인 전환 ──
    discount_eligible = (await db.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == "expired",
            Subscription.platform.in_(["trial", "promo:PRODUCTHUNT"]),
            Subscription.expires_at >= cutoff,
        )
    )).scalar() or 0

    discount_converted = (await db.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.platform == "dodopayments",
            Subscription.status == "active",
            Subscription.started_at >= cutoff,
            Subscription.user_id.in_(
                select(Subscription.user_id).where(
                    Subscription.status == "expired",
                    Subscription.platform.in_(["trial", "promo:PRODUCTHUNT"]),
                    Subscription.expires_at >= cutoff - timedelta(days=7),
                )
            )
        )
    )).scalar() or 0

    discount_conversion = round(discount_converted / max(1, discount_eligible) * 100, 1)

    # ── Referral 통계 ──
    active_referral_users = (await db.execute(
        select(func.count()).select_from(User).where(
            User.referral_pro_expires_at > now,
        )
    )).scalar() or 0

    # ── D7 리텐션 ──
    d7_start = now - timedelta(days=days + 7)
    d7_end = now - timedelta(days=7)
    yesterday = now - timedelta(days=1)

    d7_cohort = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.created_at >= d7_start, User.created_at < d7_end, User.status != "deleted")
    )).scalar() or 0

    d7_retained = (await db.execute(
        select(func.count()).select_from(User)
        .where(
            User.created_at >= d7_start,
            User.created_at < d7_end,
            User.last_active >= yesterday,
            User.status != "deleted",
        )
    )).scalar() or 0

    d7_retention = round(d7_retained / max(1, d7_cohort) * 100, 1)

    return {
        "period_days": days,
        "a1_onboarding_rate": a1_rate,
        "paywall_conversion_rate": paywall_rate,
        "trial_to_paid_rate": trial_to_paid,
        "promo_to_paid_rate": promo_to_paid,
        "discount_conversion_rate": discount_conversion,
        "d7_retention_rate": d7_retention,
        "raw": {
            **ae_counts,
            "paywall_shown": pw_shown,
            "paywall_purchase": pw_purchase,
            "trial_started": trial_started,
            "trial_converted": trial_converted,
            "promo_started": promo_started,
            "promo_converted": promo_converted,
            "discount_eligible": discount_eligible,
            "discount_converted": discount_converted,
            "active_referral_users": active_referral_users,
            "d7_cohort": d7_cohort,
            "d7_retained": d7_retained,
        },
    }


# ── KPI Snapshots ────────────────────────────────────────────────────────────

@router.get("/kpi/snapshots")
async def list_kpi_snapshots(
    weeks: int = Query(8, ge=1, le=52),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """최근 N주 KPI 스냅샷 목록."""
    result = await db.execute(
        select(WeeklyKpiSnapshot)
        .order_by(WeeklyKpiSnapshot.week_start.desc())
        .limit(weeks)
    )
    snapshots = result.scalars().all()
    return [
        {
            "id": s.id,
            "week_start": s.week_start.isoformat(),
            "week_end": s.week_end.isoformat(),
            "metrics": s.metrics,
            "kpi": s.kpi,
            "wow_delta": s.wow_delta,
            "alerts": s.alerts,
            "created_at": s.created_at.isoformat(),
        }
        for s in snapshots
    ]


@router.post("/kpi/snapshots/generate")
async def generate_kpi_snapshot(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """수동 KPI 스냅샷 생성 (직전 주)."""
    from datetime import date
    from backend.app.models.paywall_event import PaywallEvent

    now = datetime.now(timezone.utc)
    # 직전 주 월~일
    today = now.date()
    days_since_monday = today.weekday()
    this_monday = today - timedelta(days=days_since_monday)
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)

    week_start_dt = datetime.combine(last_monday, datetime.min.time()).replace(tzinfo=timezone.utc)
    week_end_dt = datetime.combine(last_sunday, datetime.max.time()).replace(tzinfo=timezone.utc)

    # 중복 체크
    existing = await db.execute(
        select(WeeklyKpiSnapshot).where(WeeklyKpiSnapshot.week_start == last_monday)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "이미 해당 주의 스냅샷이 존재합니다")

    # app_events 집계
    ae_q = await db.execute(
        select(AppEvent.name, func.count())
        .where(AppEvent.created_at >= week_start_dt, AppEvent.created_at <= week_end_dt)
        .group_by(AppEvent.name)
    )
    ae_counts = {row[0]: row[1] for row in ae_q.all()}

    auth_success = ae_counts.get("auth_success", 0)
    onboarding_complete = ae_counts.get("onboarding_complete", 0)
    a1_rate = round(onboarding_complete / max(1, auth_success) * 100, 1)

    # Paywall
    pw_shown = (await db.execute(
        select(func.count()).select_from(PaywallEvent)
        .where(PaywallEvent.action == "shown", PaywallEvent.created_at >= week_start_dt, PaywallEvent.created_at <= week_end_dt)
    )).scalar() or 0
    pw_purchase = (await db.execute(
        select(func.count()).select_from(PaywallEvent)
        .where(PaywallEvent.action == "purchase_success", PaywallEvent.created_at >= week_start_dt, PaywallEvent.created_at <= week_end_dt)
    )).scalar() or 0
    paywall_rate = round(pw_purchase / max(1, pw_shown) * 100, 1)

    # Trial → Paid
    trial_started = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(Subscription.trial_start.isnot(None), Subscription.trial_start >= week_start_dt, Subscription.trial_start <= week_end_dt)
    )).scalar() or 0
    trial_converted = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(Subscription.trial_start.isnot(None), Subscription.trial_start >= week_start_dt, Subscription.trial_start <= week_end_dt, Subscription.status == "active", Subscription.trial_end.isnot(None))
    )).scalar() or 0
    trial_to_paid = round(trial_converted / max(1, trial_started) * 100, 1)

    # D7 Retention
    d7_start = week_start_dt - timedelta(days=7)
    d7_end = week_start_dt
    d7_cohort = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= d7_start, User.created_at < d7_end, User.status != "deleted")
    )).scalar() or 0
    d7_retained = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= d7_start, User.created_at < d7_end, User.last_active >= week_start_dt, User.status != "deleted")
    )).scalar() or 0
    d7_retention = round(d7_retained / max(1, d7_cohort) * 100, 1)

    # Referral 메트릭
    referral_install = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.created_at >= week_start_dt, User.created_at <= week_end_dt, User.referred_by_code.isnot(None))
    )).scalar() or 0
    referral_trial_start = (await db.execute(
        select(func.count()).select_from(Subscription)
        .where(
            Subscription.trial_start.isnot(None),
            Subscription.trial_start >= week_start_dt,
            Subscription.trial_start <= week_end_dt,
        ).where(
            Subscription.user_id.in_(
                select(User.id).where(User.referred_by_code.isnot(None))
            )
        )
    )).scalar() or 0

    metrics = {**ae_counts, "paywall_shown": pw_shown, "paywall_purchase": pw_purchase, "trial_started": trial_started, "trial_converted": trial_converted, "d7_cohort": d7_cohort, "d7_retained": d7_retained, "referral_install": referral_install, "referral_trial_start": referral_trial_start}
    kpi_data = {"a1_onboarding_rate": a1_rate, "paywall_conversion_rate": paywall_rate, "trial_to_paid_rate": trial_to_paid, "d7_retention_rate": d7_retention}

    # WoW delta
    prev_snapshot = await db.execute(
        select(WeeklyKpiSnapshot).where(WeeklyKpiSnapshot.week_start == last_monday - timedelta(days=7))
    )
    prev = prev_snapshot.scalar_one_or_none()
    wow_delta = None
    alerts = None
    if prev and prev.kpi:
        wow_delta = {}
        alerts = []
        for k, v in kpi_data.items():
            prev_val = prev.kpi.get(k, 0)
            delta = round(v - prev_val, 1)
            wow_delta[k] = delta
            # Alert: WoW -30% drop AND prev denominator >= 10
            if prev_val > 0 and delta / prev_val * 100 <= -30:
                alerts.append({"kpi": k, "prev": prev_val, "curr": v, "drop_pct": round(delta / prev_val * 100, 1)})
        if not alerts:
            alerts = None

    snapshot = WeeklyKpiSnapshot(
        week_start=last_monday,
        week_end=last_sunday,
        metrics=metrics,
        kpi=kpi_data,
        wow_delta=wow_delta,
        alerts=alerts,
        data_source="manual",
    )
    db.add(snapshot)
    await db.flush()
    await _log_action(db, admin, "generate_kpi_snapshot", detail={"week_start": last_monday.isoformat()})
    return {"status": "ok", "week_start": last_monday.isoformat(), "kpi": kpi_data, "alerts": alerts}


# ── Partners CRM ─────────────────────────────────────────────────────────────

VALID_PARTNER_STATUSES = {"prospect", "contacted", "negotiating", "active", "churned", "rejected"}


class PartnerCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    company_type: str = "media"
    status: str = "prospect"
    channel: Optional[str] = None
    segment: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    next_follow_up: Optional[str] = None


class PartnerPatch(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    company_type: Optional[str] = None
    status: Optional[str] = None
    channel: Optional[str] = None
    segment: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    next_follow_up: Optional[str] = None


@router.get("/partners")
async def list_partners(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Partner)
    filters = []
    if status:
        filters.append(Partner.status == status)
    if segment:
        filters.append(Partner.segment == segment)
    if channel:
        filters.append(Partner.channel == channel)
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        filters.append((Partner.name.ilike(f"%{safe_search}%")) | (Partner.contact_email.ilike(f"%{safe_search}%")))
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Partner.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    partners = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(p.id),
                "name": p.name,
                "contact_name": p.contact_name,
                "contact_email": p.contact_email,
                "contact_phone": p.contact_phone,
                "company_type": p.company_type,
                "status": p.status,
                "channel": p.channel,
                "segment": p.segment,
                "url": p.url,
                "notes": p.notes,
                "next_follow_up": p.next_follow_up.isoformat() if p.next_follow_up else None,
                "last_published_at": p.last_published_at.isoformat() if p.last_published_at else None,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in partners
        ],
    }


@router.post("/partners")
async def create_partner(
    body: PartnerCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type
    if body.status not in VALID_PARTNER_STATUSES:
        raise HTTPException(422, f"Invalid status. Valid: {sorted(VALID_PARTNER_STATUSES)}")
    partner = Partner(
        name=body.name,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        company_type=body.company_type,
        status=body.status,
        channel=body.channel,
        segment=body.segment,
        url=body.url,
        notes=body.notes,
        next_follow_up=date_type.fromisoformat(body.next_follow_up) if body.next_follow_up else None,
    )
    db.add(partner)
    await db.flush()
    await _log_action(db, admin, "create_partner", "partner", str(partner.id))
    return {"status": "ok", "id": str(partner.id)}


@router.patch("/partners/{partner_id}")
async def update_partner(
    partner_id: str,
    body: PartnerPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type
    result = await db.execute(select(Partner).where(Partner.id == uuid.UUID(partner_id)))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(404)
    if body.status is not None and body.status not in VALID_PARTNER_STATUSES:
        raise HTTPException(422, f"Invalid status. Valid: {sorted(VALID_PARTNER_STATUSES)}")
    changes = {}
    for field in ["name", "contact_name", "contact_email", "contact_phone", "company_type", "status", "channel", "segment", "url", "notes"]:
        val = getattr(body, field)
        if val is not None:
            setattr(partner, field, val)
            changes[field] = val
    if body.next_follow_up is not None:
        partner.next_follow_up = date_type.fromisoformat(body.next_follow_up) if body.next_follow_up else None
        changes["next_follow_up"] = body.next_follow_up
    partner.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await _log_action(db, admin, "update_partner", "partner", partner_id, changes)
    return {"status": "ok"}


@router.delete("/partners/{partner_id}", status_code=204)
async def delete_partner(
    partner_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Partner).where(Partner.id == uuid.UUID(partner_id)))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(404)
    await db.delete(partner)
    await db.flush()
    await _log_action(db, admin, "delete_partner", "partner", partner_id)


# ── Short Links Admin ────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    target_url: str
    title: Optional[str] = None
    code: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    expires_at: Optional[str] = None


class LinkPatch(BaseModel):
    target_url: Optional[str] = None
    title: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[str] = None


@router.get("/links")
async def list_links(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(ShortLink)
    filters = []
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        filters.append((ShortLink.code.ilike(f"%{safe_search}%")) | (ShortLink.title.ilike(f"%{safe_search}%")))
    if is_active is not None:
        filters.append(ShortLink.is_active == is_active)
    if filters:
        q = q.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(ShortLink.created_at.desc()).offset((page - 1) * 20).limit(20)
    result = await db.execute(q)
    links = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(l.id),
                "code": l.code,
                "target_url": l.target_url,
                "title": l.title,
                "utm_source": l.utm_source,
                "utm_medium": l.utm_medium,
                "utm_campaign": l.utm_campaign,
                "click_count": l.click_count,
                "is_active": l.is_active,
                "created_at": l.created_at.isoformat(),
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            }
            for l in links
        ],
    }


@router.post("/links")
async def create_link(
    body: LinkCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import secrets
    code = body.code or secrets.token_urlsafe(4)[:6]
    # Check uniqueness
    existing = await db.execute(select(ShortLink).where(ShortLink.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Code '{code}' already exists")

    link = ShortLink(
        code=code,
        target_url=body.target_url,
        title=body.title,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign,
        created_by=admin.id,
        expires_at=datetime.fromisoformat(body.expires_at) if body.expires_at else None,
    )
    db.add(link)
    await db.flush()
    await _log_action(db, admin, "create_link", "link", str(link.id))
    return {"status": "ok", "id": str(link.id), "code": code}


@router.patch("/links/{link_id}")
async def update_link(
    link_id: str,
    body: LinkPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShortLink).where(ShortLink.id == uuid.UUID(link_id)))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(404)
    if body.target_url is not None:
        link.target_url = body.target_url
    if body.title is not None:
        link.title = body.title
    if body.is_active is not None:
        link.is_active = body.is_active
    if body.expires_at is not None:
        link.expires_at = datetime.fromisoformat(body.expires_at) if body.expires_at else None
    await db.flush()
    # Invalidate Redis cache
    try:
        redis = get_redis()
        await redis.delete(f"sl:{link.code}")
    except Exception as e:
        logger.debug("admin: %s", e)
    await _log_action(db, admin, "update_link", "link", link_id)
    return {"status": "ok"}


@router.delete("/links/{link_id}", status_code=204)
async def delete_link(
    link_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShortLink).where(ShortLink.id == uuid.UUID(link_id)))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(404)
    # Invalidate cache
    try:
        redis = get_redis()
        await redis.delete(f"sl:{link.code}")
    except Exception as e:
        logger.debug("admin: %s", e)
    await db.execute(delete(LinkClick).where(LinkClick.link_id == link.id))
    await db.delete(link)
    await db.flush()
    await _log_action(db, admin, "delete_link", "link", link_id)


@router.get("/links/{link_id}/clicks")
async def get_link_clicks(
    link_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LinkClick)
        .where(LinkClick.link_id == uuid.UUID(link_id))
        .order_by(LinkClick.created_at.desc())
        .limit(100)
    )
    clicks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "ip_hash": c.ip_hash,
            "user_agent": c.user_agent,
            "referer": c.referer,
            "country_code": c.country_code,
            "created_at": c.created_at.isoformat(),
        }
        for c in clicks
    ]


@router.get("/links/{link_id}/stats")
async def get_link_stats(
    link_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """일별 클릭 통계."""
    result = await db.execute(
        select(
            cast(LinkClick.created_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(LinkClick.link_id == uuid.UUID(link_id))
        .group_by("date")
        .order_by("date")
    )
    return [{"date": row.date.isoformat(), "count": row.count} for row in result.all()]


# ── Subscription Admin PATCH ─────────────────────────────────────────────────

class SubscriptionPatch(BaseModel):
    plan: Optional[str] = None
    status: Optional[str] = None


@router.patch("/subscriptions/{sub_id}")
async def update_subscription(
    sub_id: str,
    body: SubscriptionPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.id == uuid.UUID(sub_id)))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404)
    changes = {}
    if body.plan:
        # Update the user's plan too
        user_result = await db.execute(select(User).where(User.id == sub.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = body.plan
            await sync_area_activation(user.id, body.plan, db)
        changes["plan"] = body.plan
    if body.status:
        sub.status = body.status
        changes["status"] = body.status
    await db.flush()
    await _log_action(db, admin, "update_subscription", "subscription", sub_id, changes)
    return {"status": "ok"}


# ── Reports Performance ──────────────────────────────────────────────────────

@router.get("/reports/weekly-performance")
async def weekly_report_performance(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """주간 리포트 발송 성적."""
    result = await db.execute(
        text("""
            SELECT
                date_trunc('week', created_at)::date AS week,
                status,
                COUNT(*) AS cnt
            FROM marketing_email_logs
            WHERE created_at >= NOW() - INTERVAL '8 weeks'
            GROUP BY 1, 2
            ORDER BY 1 DESC
        """)
    )
    rows = result.fetchall()
    weeks = {}
    for row in rows:
        w = row.week.isoformat()
        if w not in weeks:
            weeks[w] = {"week": w, "sent": 0, "failed": 0}
        weeks[w][row.status] = row.cnt
    return list(weeks.values())


@router.get("/reports/referral-kpi")
async def referral_kpi(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """레퍼럴 성과."""
    total_codes = (await db.execute(
        select(func.count()).select_from(User).where(User.referral_code.isnot(None))
    )).scalar() or 0

    total_used = (await db.execute(
        select(func.count()).select_from(User).where(User.referred_by_code.isnot(None))
    )).scalar() or 0

    # Pro 전환 (referred users who became pro)
    pro_converted = (await db.execute(
        select(func.count()).select_from(User).where(
            User.referred_by_code.isnot(None),
            User.plan != "free",
        )
    )).scalar() or 0

    # Top referrers
    top_referrers = await db.execute(
        text("""
            SELECT u.referral_code, u.nickname,
                   (SELECT COUNT(*) FROM users r WHERE r.referred_by_code = u.referral_code) AS referred_count
            FROM users u
            WHERE u.referral_code IS NOT NULL
            ORDER BY referred_count DESC
            LIMIT 10
        """)
    )

    return {
        "total_codes": total_codes,
        "total_used": total_used,
        "pro_converted": pro_converted,
        "top_referrers": [
            {"code": r.referral_code, "nickname": r.nickname, "count": r.referred_count}
            for r in top_referrers.fetchall()
        ],
    }


# ── SNS 자동 포스팅 관리 ─────────────────────────────────────────────────────

class SocialPostUpdate(BaseModel):
    body_text: Optional[str] = None
    hashtags: Optional[list[str]] = None


@router.get("/social")
async def list_social_posts(
    status: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    per_page = 20
    query = select(SocialPost)
    count_query = select(func.count()).select_from(SocialPost)

    filters = []
    if status:
        filters.append(SocialPost.status == status)
    if content_type:
        filters.append(SocialPost.content_type == content_type)
    if q:
        filters.append(SocialPost.body_text.ilike(f"%{q}%"))

    if filters:
        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(SocialPost.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    posts = result.scalars().all()

    # 플랫폼 상태 조회
    post_ids = [p.id for p in posts]
    platforms_map: dict[uuid.UUID, list[dict]] = {pid: [] for pid in post_ids}
    if post_ids:
        plat_result = await db.execute(
            select(SocialPostPlatform).where(SocialPostPlatform.post_id.in_(post_ids))
        )
        for pp in plat_result.scalars().all():
            platforms_map[pp.post_id].append({
                "platform": pp.platform,
                "status": pp.status,
                "platform_post_id": pp.platform_post_id,
                "error_message": pp.error_message,
                "published_at": pp.published_at.isoformat() if pp.published_at else None,
            })

    # platform 필터 (post-query 필터)
    items = []
    for p in posts:
        plats = platforms_map.get(p.id, [])
        if platform:
            if not any(pp["platform"] == platform for pp in plats):
                continue
        items.append({
            "id": str(p.id),
            "content_type": p.content_type,
            "lang": p.lang,
            "body_text": p.body_text,
            "hashtags": p.hashtags or [],
            "image_url": p.image_url,
            "risk_level": p.risk_level,
            "source_cluster_id": str(p.source_cluster_id) if p.source_cluster_id else None,
            "source_spike_id": str(p.source_spike_id) if p.source_spike_id else None,
            "dedup_key": p.dedup_key,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            "approved_by": p.approved_by,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "platforms": plats,
        })

    return {"items": items, "total": total}


@router.get("/social/stats")
async def social_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    pending = (await db.execute(
        select(func.count()).select_from(SocialPost).where(SocialPost.status == "pending_review")
    )).scalar() or 0
    published_today = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "published", SocialPost.published_at >= today_start)
    )).scalar() or 0
    published_week = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "published", SocialPost.published_at >= week_start)
    )).scalar() or 0
    failed_count = (await db.execute(
        select(func.count()).select_from(SocialPost).where(SocialPost.status == "failed")
    )).scalar() or 0

    return {
        "pending": pending,
        "published_today": published_today,
        "published_week": published_week,
        "failed": failed_count,
    }


# ── 소셜 자동 승인 규칙 ───────────────────────────────────────────────

SOCIAL_AUTO_APPROVE_KEY = "admin:social:auto_approve_rules"
DEFAULT_AUTO_APPROVE_RULES = {"daily_movers": True, "weekly_report": True, "kscore_alert": False}


class AutoApproveRulesBody(BaseModel):
    daily_movers: bool = True
    weekly_report: bool = True
    kscore_alert: bool = False


@router.get("/social/auto-approve-rules")
async def get_auto_approve_rules(
    admin: User = Depends(require_admin),
):
    import json
    try:
        redis = get_redis()
        cached = await redis.get(SOCIAL_AUTO_APPROVE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug("admin: %s", e)
    return DEFAULT_AUTO_APPROVE_RULES


@router.put("/social/auto-approve-rules")
async def update_auto_approve_rules(
    body: AutoApproveRulesBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import json
    rules = body.dict()
    # kscore_alert은 항상 수동 (False 강제)
    rules["kscore_alert"] = False
    try:
        redis = get_redis()
        await redis.set(SOCIAL_AUTO_APPROVE_KEY, json.dumps(rules))
    except Exception as e:
        logger.debug("admin: %s", e)
    await _log_action(db, admin, "update_auto_approve_rules", detail=rules)
    return rules


@router.get("/social/{post_id}")
async def get_social_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    plat_result = await db.execute(
        select(SocialPostPlatform).where(SocialPostPlatform.post_id == post.id)
    )
    platforms = [
        {
            "platform": pp.platform,
            "status": pp.status,
            "platform_post_id": pp.platform_post_id,
            "error_message": pp.error_message,
            "published_at": pp.published_at.isoformat() if pp.published_at else None,
        }
        for pp in plat_result.scalars().all()
    ]

    return {
        "id": str(post.id),
        "content_type": post.content_type,
        "lang": post.lang,
        "body_text": post.body_text,
        "hashtags": post.hashtags or [],
        "image_url": post.image_url,
        "risk_level": post.risk_level,
        "source_cluster_id": str(post.source_cluster_id) if post.source_cluster_id else None,
        "source_spike_id": str(post.source_spike_id) if post.source_spike_id else None,
        "dedup_key": post.dedup_key,
        "status": post.status,
        "created_at": post.created_at.isoformat(),
        "approved_at": post.approved_at.isoformat() if post.approved_at else None,
        "approved_by": post.approved_by,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "platforms": platforms,
    }


@router.post("/social/{post_id}/approve")
async def approve_social_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    post.status = "approved"
    post.approved_at = datetime.now(timezone.utc)
    post.approved_by = admin.nickname or admin.email or str(admin.id)
    await db.flush()
    await _log_action(db, admin, "approve_social", "social_post", post_id)
    return {"status": "ok"}


@router.post("/social/{post_id}/reject")
async def reject_social_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    post.status = "rejected"
    await db.flush()
    await _log_action(db, admin, "reject_social", "social_post", post_id)
    return {"status": "ok"}


@router.post("/social/{post_id}/retry")
async def retry_social_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)
    if post.status != "failed":
        raise HTTPException(400, "Only failed posts can be retried")

    post.status = "approved"
    post.approved_at = datetime.now(timezone.utc)
    post.approved_by = admin.nickname or admin.email or str(admin.id)

    # 실패한 플랫폼 레코드 삭제 (재시도)
    await db.execute(
        delete(SocialPostPlatform).where(
            SocialPostPlatform.post_id == post.id,
            SocialPostPlatform.status == "failed",
        )
    )

    await db.flush()
    await _log_action(db, admin, "retry_social", "social_post", post_id)
    return {"status": "ok"}


@router.get("/social/{post_id}/preview")
async def preview_social_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """플랫폼별 미리보기 텍스트 반환."""
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    from worker.social.adapters.x_adapter import _build_text as x_build
    from worker.social.adapters.threads_adapter import _build_text as threads_build

    x_text = x_build(post)
    threads_text = threads_build(post)

    return {
        "x": {"text": x_text, "char_count": len(x_text), "max": 280},
        "threads": {"text": threads_text, "char_count": len(threads_text), "max": 500},
    }


@router.post("/social/{post_id}/approve/{platform}")
async def approve_social_post_platform(
    post_id: str,
    platform: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """플랫폼별 승인 — platform: x | threads | all."""
    if platform not in ("x", "threads", "all"):
        raise HTTPException(400, "platform must be x, threads, or all")

    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    post.status = "approved"
    post.approved_at = datetime.now(timezone.utc)
    post.approved_by = admin.nickname or admin.email or str(admin.id)

    # 플랫폼별 승인: 나머지 플랫폼은 skipped 처리
    skip_platforms = []
    if platform == "x":
        skip_platforms = ["threads"]
    elif platform == "threads":
        skip_platforms = ["x"]

    for skip_plat in skip_platforms:
        existing = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == skip_plat,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(SocialPostPlatform(
                post_id=post.id,
                platform=skip_plat,
                status="skipped",
            ))

    await db.flush()
    await _log_action(db, admin, "approve_social", "social_post", post_id, {"platform": platform})
    return {"status": "ok"}


@router.get("/social/chart-data")
async def social_chart_data(
    days: int = 14,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """일별 SNS 포스트 추이 데이터 (차트용)."""
    days = min(days, 90)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # 일별 생성 건수 (status별)
    daily_result = await db.execute(
        select(
            func.date_trunc("day", SocialPost.created_at).label("day"),
            SocialPost.status,
            func.count().label("cnt"),
        )
        .where(SocialPost.created_at >= cutoff)
        .group_by("day", SocialPost.status)
        .order_by("day")
    )
    daily_rows = daily_result.all()

    # 날짜별로 집계
    daily_map: dict[str, dict] = {}
    for row in daily_rows:
        day_str = row.day.strftime("%m/%d")
        if day_str not in daily_map:
            daily_map[day_str] = {"date": day_str, "published": 0, "failed": 0, "pending": 0, "rejected": 0, "total": 0}
        daily_map[day_str][row.status if row.status in ("published", "failed", "rejected") else "pending"] += row.cnt
        daily_map[day_str]["total"] += row.cnt

    daily = list(daily_map.values())

    # 플랫폼별 발행 현황
    plat_result = await db.execute(
        select(
            SocialPostPlatform.platform,
            SocialPostPlatform.status,
            func.count().label("cnt"),
        )
        .where(SocialPostPlatform.published_at >= cutoff)
        .group_by(SocialPostPlatform.platform, SocialPostPlatform.status)
    )
    plat_rows = plat_result.all()

    plat_map: dict[str, dict] = {}
    for row in plat_rows:
        if row.platform not in plat_map:
            plat_map[row.platform] = {"platform": row.platform, "published": 0, "failed": 0, "skipped": 0}
        plat_map[row.platform][row.status if row.status in ("published", "failed", "skipped") else "published"] += row.cnt

    platforms = list(plat_map.values())

    # 콘텐츠 타입별 통계
    type_result = await db.execute(
        select(
            SocialPost.content_type,
            func.count().label("cnt"),
        )
        .where(SocialPost.created_at >= cutoff)
        .group_by(SocialPost.content_type)
    )
    content_types = [{"type": row.content_type, "count": row.cnt} for row in type_result.all()]

    # 언어별 통계
    lang_result = await db.execute(
        select(
            SocialPost.lang,
            func.count().label("cnt"),
        )
        .where(SocialPost.created_at >= cutoff)
        .group_by(SocialPost.lang)
    )
    langs = [{"lang": row.lang, "count": row.cnt} for row in lang_result.all()]

    return {
        "daily": daily,
        "platforms": platforms,
        "content_types": content_types,
        "langs": langs,
    }


@router.patch("/social/{post_id}")
async def update_social_post(
    post_id: str,
    body: SocialPostUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialPost).where(SocialPost.id == uuid.UUID(post_id))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    changes = {}
    if body.body_text is not None:
        post.body_text = body.body_text[:500]
        changes["body_text"] = body.body_text[:50] + "..."
    if body.hashtags is not None:
        post.hashtags = body.hashtags
        changes["hashtags"] = body.hashtags

    await db.flush()
    await _log_action(db, admin, "update_social", "social_post", post_id, changes)
    return {"status": "ok"}


# ── 주간 리포트 관리 ──────────────────────────────────────────────────────────

class WeeklyReportDraftBody(BaseModel):
    editor_note_ko: Optional[str] = None
    editor_note_en: Optional[str] = None
    issue_ids: Optional[list[str]] = None  # 순서가 있는 이슈 ID 목록


@router.get("/weekly-report/draft")
async def get_weekly_report_draft(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """현재 주간 리포트 초안 데이터 반환."""
    import json as _json

    redis = await get_redis()
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%Y-W%W")
    draft_key = f"admin:weekly-report:draft:{week_key}"

    # 저장된 초안 로드
    raw = await redis.get(draft_key)
    draft = _json.loads(raw) if raw else {}

    # 기본 데이터: 공개 weekly-summary와 동일한 로직
    cutoff = now - timedelta(days=7)

    top_clusters_q = await db.execute(
        select(
            IssueCluster.id,
            IssueCluster.title,
            IssueCluster.title_ko,
            IssueCluster.severity,
            IssueCluster.kscore,
            IssueCluster.event_count,
            IssueCluster.country_code,
            IssueCluster.topic,
        )
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(20)  # 편집 가능하도록 넉넉히 가져옴
    )
    all_issues = [
        {
            "id": str(row.id),
            "title": row.title,
            "title_ko": row.title_ko,
            "severity": row.severity,
            "kscore": round(row.kscore, 2),
            "event_count": row.event_count,
            "country_code": row.country_code,
            "topic": row.topic,
        }
        for row in top_clusters_q.all()
    ]

    # 초안에서 순서/제외 적용
    ordered_ids = draft.get("issue_ids")
    if ordered_ids:
        id_map = {iss["id"]: iss for iss in all_issues}
        top_issues = [id_map[iid] for iid in ordered_ids if iid in id_map]
    else:
        top_issues = all_issues[:10]

    # 긴장도 TOP 10
    from sqlalchemy import func as sa_func
    latest_tension_subq = (
        select(
            TensionIndex.country_code,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            sa_func.row_number()
            .over(partition_by=TensionIndex.country_code, order_by=TensionIndex.time.desc())
            .label("rn"),
        ).subquery()
    )
    tension_q = await db.execute(
        select(
            latest_tension_subq.c.country_code,
            latest_tension_subq.c.raw_score,
            latest_tension_subq.c.tension_level,
        )
        .where(latest_tension_subq.c.rn == 1)
        .order_by(latest_tension_subq.c.raw_score.desc())
        .limit(10)
    )
    top_tension = [
        {"country_code": row.country_code, "raw_score": round(row.raw_score, 1), "tension_level": row.tension_level}
        for row in tension_q.all()
    ]

    # 통계
    total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= cutoff)
    )).scalar() or 0
    new_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.created_at >= cutoff, IssueCluster.severity > 0)
    )).scalar() or 0
    crisis_q = await db.execute(
        select(latest_tension_subq.c.country_code)
        .where(latest_tension_subq.c.rn == 1, latest_tension_subq.c.tension_level >= 3)
    )
    crisis_countries = len(crisis_q.all())

    # 발송 대상 수
    target_count = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.marketing_agreed_at != None, User.status != "deleted", User.email != None)
    )).scalar() or 0

    return {
        "week": week_key,
        "editor_note_ko": draft.get("editor_note_ko", ""),
        "editor_note_en": draft.get("editor_note_en", ""),
        "top_issues": top_issues,
        "all_issues": all_issues,
        "top_tension": top_tension,
        "stats": {
            "total_events": total_events,
            "new_clusters": new_clusters,
            "crisis_countries": crisis_countries,
        },
        "target_count": target_count,
    }


@router.put("/weekly-report/draft")
async def save_weekly_report_draft(
    body: WeeklyReportDraftBody,
    admin: User = Depends(require_admin),
):
    """초안 저장 (에디터 노트, 이슈 순서)."""
    import json as _json

    redis = await get_redis()
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%Y-W%W")
    draft_key = f"admin:weekly-report:draft:{week_key}"

    raw = await redis.get(draft_key)
    draft = _json.loads(raw) if raw else {}

    if body.editor_note_ko is not None:
        draft["editor_note_ko"] = body.editor_note_ko
    if body.editor_note_en is not None:
        draft["editor_note_en"] = body.editor_note_en
    if body.issue_ids is not None:
        draft["issue_ids"] = body.issue_ids

    await redis.set(draft_key, _json.dumps(draft), ex=30 * 24 * 3600)  # 30일 TTL

    return {"status": "ok"}


@router.post("/weekly-report/send-test")
async def send_weekly_report_test(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """어드민 본인에게 테스트 발송."""
    from mako.template import Template
    import json as _json

    if not admin.email:
        raise HTTPException(400, detail="Admin email not found")

    # 초안 로드
    redis = await get_redis()
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%Y-W%W")
    raw = await redis.get(f"admin:weekly-report:draft:{week_key}")
    draft = _json.loads(raw) if raw else {}

    # 데이터 가져오기 (간소 버전 — draft API와 동일 로직)
    cutoff = now - timedelta(days=7)
    top_clusters_q = await db.execute(
        select(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(10)
    )
    issues = top_clusters_q.scalars().all()

    from sqlalchemy import func as sa_func
    latest_tension_subq = (
        select(
            TensionIndex.country_code,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            sa_func.row_number()
            .over(partition_by=TensionIndex.country_code, order_by=TensionIndex.time.desc())
            .label("rn"),
        ).subquery()
    )
    tension_q = await db.execute(
        select(
            latest_tension_subq.c.country_code,
            latest_tension_subq.c.raw_score,
            latest_tension_subq.c.tension_level,
        )
        .where(latest_tension_subq.c.rn == 1)
        .order_by(latest_tension_subq.c.raw_score.desc())
        .limit(10)
    )
    tensions = [type("T", (), {"country_code": r.country_code, "raw_score": r.raw_score, "tension_level": r.tension_level}) for r in tension_q.all()]

    total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= cutoff)
    )).scalar() or 0
    new_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.created_at >= cutoff, IssueCluster.severity > 0)
    )).scalar() or 0

    # 렌더링
    import os
    tpl_path = os.path.join(os.path.dirname(__file__), "..", "templates", "weekly_report.html")
    tpl = Template(filename=tpl_path)
    html = tpl.render(
        lang="ko",
        user=admin,
        issues=issues,
        tensions=tensions,
        stats={"total_events": total_events, "new_clusters": new_clusters, "crisis_countries": 0},
        is_pro=True,
        editor_note=draft.get("editor_note_ko", ""),
    )

    # 발송
    try:
        _send_email(admin.email, "[TEST] WeWantPeace Weekly Report", html)
    except Exception as e:
        raise HTTPException(500, detail=f"이메일 발송 실패: {str(e)}")

    await _log_action(db, admin, "weekly_report_test_send")
    return {"status": "ok", "sent_to": admin.email}


@router.post("/weekly-report/send")
async def send_weekly_report_all(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 대상 주간 리포트 발송."""
    from backend.app.core.config import settings
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from mako.template import Template
    import json as _json

    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(503, detail="SMTP not configured")

    # 초안 로드
    redis = await get_redis()
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%Y-W%W")
    raw = await redis.get(f"admin:weekly-report:draft:{week_key}")
    draft = _json.loads(raw) if raw else {}

    # 대상 유저
    result = await db.execute(
        select(User).where(
            User.marketing_agreed_at != None, User.status != "deleted", User.email != None
        )
    )
    users = result.scalars().all()
    if not users:
        raise HTTPException(400, detail="No recipients")

    # 데이터
    cutoff = now - timedelta(days=7)
    top_clusters_q = await db.execute(
        select(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(10)
    )
    issues = top_clusters_q.scalars().all()

    from sqlalchemy import func as sa_func
    latest_tension_subq = (
        select(
            TensionIndex.country_code,
            TensionIndex.raw_score,
            TensionIndex.tension_level,
            sa_func.row_number()
            .over(partition_by=TensionIndex.country_code, order_by=TensionIndex.time.desc())
            .label("rn"),
        ).subquery()
    )
    tension_q = await db.execute(
        select(
            latest_tension_subq.c.country_code,
            latest_tension_subq.c.raw_score,
            latest_tension_subq.c.tension_level,
        )
        .where(latest_tension_subq.c.rn == 1)
        .order_by(latest_tension_subq.c.raw_score.desc())
        .limit(10)
    )
    tensions = [type("T", (), {"country_code": r.country_code, "raw_score": r.raw_score, "tension_level": r.tension_level}) for r in tension_q.all()]

    total_events = (await db.execute(
        select(func.count()).select_from(NormalizedEvent).where(NormalizedEvent.created_at >= cutoff)
    )).scalar() or 0
    new_clusters = (await db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.created_at >= cutoff, IssueCluster.severity > 0)
    )).scalar() or 0

    import os
    tpl_path = os.path.join(os.path.dirname(__file__), "..", "templates", "weekly_report.html")
    tpl = Template(filename=tpl_path)
    stats_data = {"total_events": total_events, "new_clusters": new_clusters, "crisis_countries": 0}

    # 로그 생성
    log = MarketingEmailLog(
        admin_id=admin.id,
        subject="WeWantPeace Weekly Report",
        body="[weekly-report]",
        sent_count=0,
        failed_count=0,
        status="sending",
    )
    db.add(log)
    await db.flush()

    # 각 유저별 렌더링 + 발송
    recipients = []
    for u in users:
        try:
            lang = getattr(u, "lang", None) or "ko"
            is_pro = getattr(u, "plan", "free") != "free"
            note = draft.get(f"editor_note_{lang}", "") or draft.get("editor_note_ko", "")
            html = tpl.render(
                lang=lang,
                user=u,
                issues=issues,
                tensions=tensions if is_pro else [],
                stats=stats_data,
                is_pro=is_pro,
                editor_note=note,
            )
            subj = "WeWantPeace 주간 리포트" if lang == "ko" else "WeWantPeace Weekly Report"
            recipients.append((u.email, subj, html))
        except Exception:
            pass

    try:
        result = _send_email_bulk(recipients)
        sent = result["sent"]
        failed = result["failed"]
    except Exception as e:
        log.status = "failed"
        log.failed_count = len(users)
        await db.flush()
        raise HTTPException(500, detail=f"이메일 발송 실패: {str(e)}")

    log.sent_count = sent
    log.failed_count = failed
    log.status = "completed"
    await db.flush()
    await _log_action(db, admin, "weekly_report_send", detail={"sent": sent, "failed": failed})

    return {"status": "ok", "sent": sent, "failed": failed}


@router.get("/weekly-report/history")
async def weekly_report_history(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """주간 리포트 발송 기록."""
    result = await db.execute(
        select(MarketingEmailLog)
        .where(MarketingEmailLog.subject.contains("Weekly Report"))
        .order_by(MarketingEmailLog.created_at.desc())
        .limit(20)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "date": l.created_at.isoformat() if l.created_at else None,
            "sent": l.sent_count,
            "failed": l.failed_count,
            "status": l.status,
        }
        for l in logs
    ]


# ────────────────────────────────────────────────────────────────
# Newsletter (Handlebars template editor + renderer)
# ────────────────────────────────────────────────────────────────

class NewsletterDraftBody(BaseModel):
    vol: int
    lang: str  # "kr" | "us"
    data: dict


class NewsletterRenderBody(BaseModel):
    lang: str  # "kr" | "us"
    data: dict


class NewsletterSendTestBody(BaseModel):
    lang: str = "kr"
    data: dict


def _newsletter_template_dir() -> Path:
    """Return the path to backend/app/templates/newsletter/."""
    import os
    return Path(os.path.dirname(__file__)).parent / "templates" / "newsletter"


def _load_sample_data(lang: str) -> dict:
    """Load vol1 sample JSON and resolve @file: block references."""
    tpl_dir = _newsletter_template_dir()
    fname = "vol1-kr-sample.json" if lang == "kr" else "vol1-us-sample.json"
    sample_path = tpl_dir / fname
    if not sample_path.exists():
        return {}
    import json as _json
    with open(sample_path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    # Resolve @file: references so the editor gets actual HTML
    for key, value in list(data.items()):
        if isinstance(value, str) and value.startswith("@file:"):
            ref_path = tpl_dir.parent.parent.parent.parent / "docs" / "marketing" / value[6:]
            if not ref_path.exists():
                ref_path = tpl_dir / value[6:]
            if ref_path.exists():
                with open(ref_path, "r", encoding="utf-8") as f:
                    data[key] = f.read()
    # Strip internal keys
    data.pop("_comment", None)
    data.pop("_template", None)
    return data


@router.get("/newsletter/draft")
async def get_newsletter_draft(
    vol: int = Query(1),
    lang: str = Query("kr"),
    admin: User = Depends(require_admin),
):
    """뉴스레터 초안 로드. Redis에 없으면 샘플 데이터 반환."""
    import json as _json

    redis = await get_redis()
    draft_key = f"admin:newsletter:draft:vol{vol}-{lang}"
    raw = await redis.get(draft_key)
    if raw:
        return _json.loads(raw)
    # 기본 샘플 데이터 반환
    return _load_sample_data(lang)


@router.put("/newsletter/draft")
async def save_newsletter_draft(
    body: NewsletterDraftBody,
    admin: User = Depends(require_admin),
):
    """뉴스레터 초안 저장 (Redis, TTL 90일)."""
    import json as _json

    redis = await get_redis()
    draft_key = f"admin:newsletter:draft:vol{body.vol}-{body.lang}"
    await redis.set(draft_key, _json.dumps(body.data, ensure_ascii=False), ex=90 * 24 * 3600)
    return {"status": "ok"}


@router.delete("/newsletter/draft")
async def delete_newsletter_draft(
    vol: int = Query(1),
    lang: str = Query("kr"),
    admin: User = Depends(require_admin),
):
    """뉴스레터 초안 삭제 → 다음 로드 시 깨끗한 샘플 데이터 반환."""
    redis = await get_redis()
    draft_key = f"admin:newsletter:draft:vol{vol}-{lang}"
    await redis.delete(draft_key)
    return {"status": "ok", "message": f"Draft vol{vol}-{lang} deleted. Will load sample on next request."}


@router.post("/newsletter/render")
async def render_newsletter(
    body: NewsletterRenderBody,
    admin: User = Depends(require_admin),
):
    """Chevron(Mustache)으로 뉴스레터 렌더링 → HTML + 사이즈 + 미해결 변수."""
    import chevron
    import re

    tpl_dir = _newsletter_template_dir()
    tpl_name = "newsletter-v1-final-ko.html" if body.lang == "kr" else "newsletter-v1-final-en.html"
    tpl_path = tpl_dir / tpl_name
    if not tpl_path.exists():
        raise HTTPException(404, detail=f"Template not found: {tpl_name}")

    with open(tpl_path, "r", encoding="utf-8") as f:
        template = f.read()

    rendered = chevron.render(template, body.data)
    size_kb = round(len(rendered.encode("utf-8")) / 1024, 1)

    # 미해결 변수 탐지
    unresolved = list(set(re.findall(r"\{\{([^}]+)\}\}", rendered)))

    return {"html": rendered, "size_kb": size_kb, "unresolved": unresolved}


@router.post("/newsletter/send-test")
async def send_newsletter_test(
    body: NewsletterSendTestBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """어드민 본인에게 렌더된 뉴스레터 테스트 발송."""
    import chevron

    if not admin.email:
        raise HTTPException(400, detail="Admin email not found")

    # 렌더링
    tpl_dir = _newsletter_template_dir()
    tpl_name = "newsletter-v1-final-ko.html" if body.lang == "kr" else "newsletter-v1-final-en.html"
    tpl_path = tpl_dir / tpl_name
    if not tpl_path.exists():
        raise HTTPException(404, detail=f"Template not found: {tpl_name}")

    with open(tpl_path, "r", encoding="utf-8") as f:
        template = f.read()

    html = chevron.render(template, body.data)

    vol = body.data.get("vol_number", "?")
    # 이메일 제목: hero_headline_html → preheader_text 순서로 fallback
    import re as _re
    from datetime import datetime as _dt, timedelta as _td
    def _clean_html_t(s: str) -> str:
        s = _re.sub(r'<br\s*/?>', ' ', s)
        s = _re.sub(r'<[^>]+>', '', s).replace('\n', ' ')
        return _re.sub(r'\s+', ' ', s).strip()
    _headline_text = _clean_html_t(body.data.get("hero_headline_html", ""))
    if not _headline_text:
        _pre = _clean_html_t(body.data.get("preheader_text", ""))
        _headline_text = _pre.split(" — ")[0].strip() if _pre else ""
    _date_range = ""
    try:
        _end = _dt.strptime(body.data.get("issue_date", ""), "%Y.%m.%d")
        _start = _end - _td(days=6)
        _date_range = f"{_start.month}.{_start.day}~{_end.month}.{_end.day}"
    except Exception:
        pass
    _suffix = f" — WeWantPeace Vol.{vol}"
    if _date_range:
        _suffix += f" ({_date_range})"
    subject = f"[TEST] {_headline_text}{_suffix}" if _headline_text else f"[TEST] WeWantPeace Newsletter Vol.{vol}"

    try:
        _send_email(admin.email, subject, html)
    except Exception as e:
        raise HTTPException(500, detail=f"이메일 발송 실패: {str(e)}")

    await _log_action(db, admin, "newsletter_test_send", detail={"vol": vol, "lang": body.lang})
    return {"status": "ok", "sent_to": admin.email}


@router.get("/newsletter/templates")
async def list_newsletter_templates(
    admin: User = Depends(require_admin),
):
    """사용 가능한 템플릿 목록 + 변수 키 목록."""
    sample_kr = _load_sample_data("kr")
    sample_us = _load_sample_data("us")
    return {
        "templates": [
            {"lang": "kr", "name": "newsletter-v1-final-ko.html", "variable_count": len(sample_kr)},
            {"lang": "us", "name": "newsletter-v1-final-en.html", "variable_count": len(sample_us)},
        ],
        "sample_kr": sample_kr,
        "sample_us": sample_us,
    }


class NewsletterSendAllBody(BaseModel):
    vol: int
    lang: str = "kr"
    data: dict


@router.post("/newsletter/send")
async def send_newsletter_all(
    body: NewsletterSendAllBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 마케팅 동의 유저에게 뉴스레터 발송."""
    import chevron
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from backend.app.core.config import settings

    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(503, detail="SMTP not configured")

    # 대상 유저
    result = await db.execute(
        select(User).where(
            User.marketing_agreed_at != None, User.status != "deleted", User.email != None
        )
    )
    users = result.scalars().all()
    if not users:
        raise HTTPException(400, detail="No recipients")

    # 렌더링
    tpl_dir = _newsletter_template_dir()
    tpl_name = "newsletter-v1-final-ko.html" if body.lang == "kr" else "newsletter-v1-final-en.html"
    tpl_path = tpl_dir / tpl_name
    if not tpl_path.exists():
        raise HTTPException(404, detail=f"Template not found: {tpl_name}")

    with open(tpl_path, "r", encoding="utf-8") as f:
        template = f.read()

    vol = body.data.get("vol_number", body.vol)
    # 이메일 제목: hero_headline_html → preheader_text 순서로 fallback
    import re as _re
    from datetime import datetime as _dt, timedelta as _td
    def _clean_html(s: str) -> str:
        s = _re.sub(r'<br\s*/?>', ' ', s)
        s = _re.sub(r'<[^>]+>', '', s).replace('\n', ' ')
        return _re.sub(r'\s+', ' ', s).strip()
    _headline_text = _clean_html(body.data.get("hero_headline_html", ""))
    if not _headline_text:
        # hero 없으면 preheader(stats 포함)의 — 이전 부분 사용
        _pre = _clean_html(body.data.get("preheader_text", ""))
        _headline_text = _pre.split(" — ")[0].strip() if _pre else ""
    _date_range = ""
    try:
        _end = _dt.strptime(body.data.get("issue_date", ""), "%Y.%m.%d")
        _start = _end - _td(days=6)
        _date_range = f"{_start.month}.{_start.day}~{_end.month}.{_end.day}"
    except Exception:
        pass
    _suffix = f" — WeWantPeace Vol.{vol}"
    if _date_range:
        _suffix += f" ({_date_range})"
    subject_text = f"{_headline_text}{_suffix}" if _headline_text else f"WeWantPeace Newsletter Vol.{vol}"

    # 로그 생성
    log = MarketingEmailLog(
        admin_id=admin.id,
        subject=subject_text,
        body=f"[newsletter-vol{vol}-{body.lang}]",
        sent_count=0,
        failed_count=0,
        status="sending",
    )
    db.add(log)
    await db.flush()

    # 유저별 렌더링 + 발송
    from backend.app.core.config import settings as _cfg
    recipients = []
    for u in users:
        try:
            token = hmac.new(_cfg.secret_key.encode(), str(u.id).encode(), sha256).hexdigest()[:32]
            user_data = {**body.data, "unsubscribe_url": f"https://wewantpeace.live/unsubscribe?token={token}"}
            user_html = chevron.render(template, user_data)
            recipients.append((u.email, subject_text, user_html))
        except Exception:
            pass

    try:
        result = _send_email_bulk(recipients)
        sent = result["sent"]
        failed = result["failed"]
    except Exception as e:
        log.status = "failed"
        log.failed_count = len(users)
        await db.flush()
        raise HTTPException(500, detail=f"이메일 발송 실패: {str(e)}")

    log.sent_count = sent
    log.failed_count = failed
    log.status = "completed"
    await db.flush()
    await _log_action(db, admin, "newsletter_send", detail={"vol": vol, "lang": body.lang, "sent": sent, "failed": failed})

    # 아카이브용 HTML 저장 (수신거부 URL을 #으로 대체한 범용 버전)
    try:
        archive_html = chevron.render(template, {**body.data, "unsubscribe_url": "#"})
        r = get_redis()
        await r.set(f"newsletter:archive:{log.id}", archive_html, ex=365 * 86400)
    except Exception:
        pass  # 아카이브 저장 실패해도 발송은 성공으로 처리

    return {"status": "ok", "sent": sent, "failed": failed}


@router.get("/newsletter/history")
async def newsletter_history(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """뉴스레터 발송 기록."""
    result = await db.execute(
        select(MarketingEmailLog)
        .where(MarketingEmailLog.subject.contains("Newsletter"))
        .order_by(MarketingEmailLog.created_at.desc())
        .limit(20)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "date": l.created_at.isoformat() if l.created_at else None,
            "subject": l.subject,
            "sent": l.sent_count,
            "failed": l.failed_count,
            "status": l.status,
        }
        for l in logs
    ]


@router.post("/newsletter/schedule")
async def schedule_newsletter_send(
    body: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """뉴스레터 자동 발송 ON/OFF 토글. body: {enabled: true/false}"""
    enabled = body.get("enabled", True)

    redis = await get_redis()
    await redis.set("newsletter:auto_send", "1" if enabled else "0")
    await _log_action(db, admin, "newsletter_auto_send_toggle", detail={"enabled": enabled})

    return {
        "enabled": enabled,
        "schedule": {
            "asia": "Monday 09:00 KST (00:00 UTC)",
            "europe": "Monday 09:00 CET (08:00 UTC)",
            "americas": "Monday 09:00 EST (14:00 UTC)",
        },
    }


@router.get("/newsletter/schedule")
async def get_newsletter_schedule(
    admin: User = Depends(require_admin),
):
    """현재 뉴스레터 자동 발송 상태."""
    redis = await get_redis()
    auto_send = await redis.get("newsletter:auto_send")
    # 기본값: ON (사용자 요청 — 항상 켜진 상태가 기본)
    enabled = auto_send != "0"
    latest_vol_raw = await redis.get("newsletter:latest_draft_vol")
    latest_vol = int(latest_vol_raw) if latest_vol_raw else None

    return {
        "enabled": enabled,
        "latest_vol": latest_vol,
        "schedule": {
            "asia": "Monday 09:00 KST (00:00 UTC)",
            "europe": "Monday 09:00 CET (08:00 UTC)",
            "americas": "Monday 09:00 EST (14:00 UTC)",
        },
    }


@router.post("/cache/clear")
async def clear_cache(
    admin: User = Depends(require_admin),
    pattern: str = "impact:summary:*",
):
    """Redis 캐시 패턴 삭제. 기본값: impact summary 캐시."""
    redis = await get_redis()
    deleted = 0
    async for key in redis.scan_iter(pattern):
        await redis.delete(key)
        deleted += 1
    return {"deleted": deleted, "pattern": pattern}


# ── DodoPayments 구독 동기화 (웹훅 실패 복구) ───────��────────────────────────


async def _backfill_payment_candidates(db: AsyncSession, candidates: list) -> tuple[int, int]:
    """Dodo 결제 후보들을 payment_history에 적재/갱신.

    candidates: (payment, local_sub, mapped_status) 튜플 리스트.
    반환: (새로 적재한 건수, success→refunded로 갱신한 건수).

    예전엔 pg_transaction_id가 이미 있으면 무조건 스킵했는데, 그러면 처음 success로
    들어간 결제가 나중에 Dodo에서 refunded로 바뀌어도 "이미 있음"으로 건너뛰어서
    매출(success 행만 집계)에서 영영 안 빠지는 버그가 있었다.
    그래서 txn별로 어떤 상태들이 이미 있는지(+ 행 객체)를 들고 있다가,
    refunded가 새로 오면 기존 success 행을 refunded로 갱신한다.
    """
    backfilled = 0
    refunded = 0

    candidate_ids = [p.payment_id for p, _, _ in candidates]
    existing_by_txn: dict[str, dict[str, PaymentHistory]] = {}
    if candidate_ids:
        existing_rows = await db.execute(
            select(PaymentHistory).where(
                PaymentHistory.platform == "dodopayments",
                PaymentHistory.pg_transaction_id.in_(candidate_ids),
            )
        )
        for row in existing_rows.scalars().all():
            existing_by_txn.setdefault(row.pg_transaction_id, {})[row.status] = row

    for p, local_sub, mapped in candidates:
        statuses = existing_by_txn.setdefault(p.payment_id, {})

        # 같은 상태로 이미 기록돼 있으면 진짜 중복 → 스킵
        if mapped in statuses:
            continue

        # 환불이 새로 도착했는데 기존에 success 행이 있으면,
        # 새 행을 넣지 말고 그 success 행을 refunded로 갱신(매출에서 차감).
        if mapped == "refunded" and "success" in statuses:
            success_row = statuses.pop("success")
            success_row.status = "refunded"
            statuses["refunded"] = success_row
            refunded += 1
            continue

        row = PaymentHistory(
            user_id=local_sub.user_id,
            subscription_id=local_sub.id,
            amount=p.total_amount,
            currency=str(p.currency) if p.currency else "USD",
            status=mapped,
            platform="dodopayments",
            pg_transaction_id=p.payment_id,
            created_at=p.created_at,  # 매출 집계 정확성: 실제 결제 시각 보존
        )
        db.add(row)
        statuses[mapped] = row  # 같은 응답 내 중복 방어
        backfilled += 1

    return backfilled, refunded


@router.post("/sync-dodo-subscriptions")
async def sync_dodo_subscriptions(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    DodoPayments API에서 active 구독 목록을 조회하여 DB와 동기화.
    웹훅 실패 시 수동 복구용.
    """
    from backend.app.core.config import settings
    from backend.app.services.area_activation import sync_area_activation

    if not settings.dodo_api_key:
        raise HTTPException(500, detail="DODO_API_KEY 미설정")

    from dodopayments import DodoPayments as DodoClient

    client = DodoClient(
        bearer_token=settings.dodo_api_key,
        environment=settings.dodo_environment,
    )

    # DodoPayments에서 active 구독 가져오기
    dodo_subs = client.subscriptions.list(page_size=100)
    synced = 0
    errors = []

    now = datetime.now(timezone.utc)

    for dsub in dodo_subs.items:
        if dsub.status != "active":
            continue

        metadata = dsub.metadata or {}
        user_id_str = metadata.get("user_id", "")
        plan = metadata.get("plan", "")
        billing_interval = metadata.get("billing_interval", "monthly")

        if not user_id_str or not plan:
            errors.append(f"sub={dsub.subscription_id}: metadata 누락 (user_id={user_id_str}, plan={plan})")
            continue

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            errors.append(f"sub={dsub.subscription_id}: 잘못된 user_id={user_id_str}")
            continue

        # DB에 이미 이 dodo_subscription_id가 있는지 확인
        existing_result = await db.execute(
            select(Subscription).where(
                Subscription.dodo_subscription_id == dsub.subscription_id,
            ).limit(1)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # 이미 존재하면 상태만 업데���트
            if existing.status != "active":
                existing.status = "active"
                existing.updated_at = now
                synced += 1
            continue

        # 새 구독 레��드 생성
        # 기존 trial/active 구독 만료 처리
        old_result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trial", "grace_period"]),
            )
        )
        for old_sub in old_result.scalars().all():
            old_sub.status = "expired" if old_sub.status == "trial" else "cancelled"
            old_sub.cancelled_at = now
            old_sub.updated_at = now

        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            platform="dodopayments",
            amount=dsub.recurring_pre_tax_amount or 0,
            currency=str(dsub.currency) if dsub.currency else "USD",
            billing_interval=billing_interval,
            dodo_subscription_id=dsub.subscription_id,
            dodo_customer_id=dsub.customer.customer_id if dsub.customer else None,
            dodo_product_id=dsub.product_id,
            auto_renewing=True,
            started_at=dsub.created_at or now,
            expires_at=dsub.next_billing_date,
            next_billing_at=dsub.next_billing_date,
        )
        db.add(sub)

        # user.plan 업데이트
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user and not user.admin_plan_override:
            user.plan = plan
            await sync_area_activation(user_id, plan, db)

        synced += 1

    # 새로 만든 구독 레코드에 id를 부여(백필 단계에서 subscription_id로 연결하기 위해)
    await db.flush()

    # ── Dodo 결제 내역 백필 ──────────────────────────────────────────────
    # 웹훅이 403으로 막혀 payment_history에 안 들어간 과거 결제를 Dodo API에서
    # 직접 긁어와 채운다. 매출(monthly_revenue)은 payment_history.created_at
    # 기준 집계라서, created_at은 반드시 Dodo 결제 실제 시각으로 넣는다.
    payments_backfilled = 0
    payments_skipped_no_sub = 0
    payments_refunded = 0
    payments_linked = 0

    try:
        all_payments = list(client.payments.list(page_size=100))
    except Exception as e:  # noqa: BLE001 - 외부 API 실패는 errors로 보고
        all_payments = []
        errors.append(f"payments.list 실패: {e}")

    if all_payments:
        # 결제가 가리키는 dodo 구독들에 대응하는 로컬 Subscription 조회
        dodo_sub_ids = {p.subscription_id for p in all_payments if p.subscription_id}
        local_subs: dict[str, Subscription] = {}
        if dodo_sub_ids:
            sub_rows = await db.execute(
                select(Subscription).where(
                    Subscription.dodo_subscription_id.in_(dodo_sub_ids)
                )
            )
            for s in sub_rows.scalars().all():
                local_subs[s.dodo_subscription_id] = s

        # 웹훅이 payment.succeeded를 먼저 받아 subscription_id=NULL로 보존해 둔 결제행을,
        # 이제 (위에서 새로 만들었거나 이미 있던) 구독에 연결한다. subscription.active 웹훅이
        # 끝내 안 와도 sync가 한 번 돌면 고아 결제행이 구독에 붙는다.
        from backend.app.routers.dodopayments import _link_orphan_payments
        for s in local_subs.values():
            payments_linked += await _link_orphan_payments(db, s)

        def _map_status(p) -> str | None:
            """Dodo 결제 상태 → payment_history.status. 최종 상태만 기록."""
            if getattr(p, "refund_status", None) is not None:
                return "refunded"
            if p.status == "succeeded":
                return "success"
            if p.status in ("failed", "cancelled"):
                return "failed"
            return None  # processing/requires_* 등 미확정 상태는 건너뜀

        # 기록 대상(최종 상태 + 로컬 구독 매칭 가능) 후보 수집
        candidates = []  # (payment, local_sub, mapped_status)
        for p in all_payments:
            mapped = _map_status(p)
            if mapped is None:
                continue
            local_sub = local_subs.get(p.subscription_id) if p.subscription_id else None
            if local_sub is None:
                payments_skipped_no_sub += 1
                continue
            candidates.append((p, local_sub, mapped))

        payments_backfilled, payments_refunded = await _backfill_payment_candidates(db, candidates)

    await db.commit()

    return {
        "synced": synced,
        "total_active_in_dodo": sum(1 for s in dodo_subs.items if s.status == "active"),
        "payments_backfilled": payments_backfilled,
        "payments_refunded": payments_refunded,
        "payments_skipped_no_sub": payments_skipped_no_sub,
        "payments_linked": payments_linked,
        "errors": errors,
    }
