"""SNS 운영 리포트 — 일일/주간 Telegram 리포트 자동 전송."""
import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.social_post import SocialPost, SocialPostPlatform

logger = logging.getLogger(__name__)

SOCIAL_TG_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
SOCIAL_TG_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")


async def _send_telegram(text: str) -> bool:
    """Telegram 채널에 메시지 전송."""
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.warning("Telegram 봇 미설정, 리포트 전송 건너뜀")
        return False

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": SOCIAL_TG_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            if resp.status_code == 200:
                return True
            logger.error("Telegram 리포트 전송 오류: %s", resp.text)
            return False
    except Exception:
        logger.exception("Telegram 리포트 전송 실패")
        return False


async def send_daily_ops_report(db: AsyncSession) -> dict:
    """일일 SNS 운영 리포트 생성 + Telegram 전송."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 오늘 생성된 포스트 통계
    created = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.created_at >= today_start)
    )).scalar() or 0

    approved = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.approved_at >= today_start)
    )).scalar() or 0

    published = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "published", SocialPost.published_at >= today_start)
    )).scalar() or 0

    failed = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "failed", SocialPost.created_at >= today_start)
    )).scalar() or 0

    pending = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "pending_review")
    )).scalar() or 0

    rejected = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "rejected", SocialPost.created_at >= today_start)
    )).scalar() or 0

    # 콘텐츠 타입별
    type_stats = (await db.execute(
        select(SocialPost.content_type, func.count())
        .where(SocialPost.created_at >= today_start)
        .group_by(SocialPost.content_type)
    )).all()
    type_lines = [f"  • {ct}: {cnt}건" for ct, cnt in type_stats]

    # 플랫폼별 발행 현황
    plat_stats = (await db.execute(
        select(
            SocialPostPlatform.platform,
            SocialPostPlatform.status,
            func.count(),
        )
        .where(SocialPostPlatform.published_at >= today_start)
        .group_by(SocialPostPlatform.platform, SocialPostPlatform.status)
    )).all()
    plat_lines = [f"  • {plat} [{st}]: {cnt}건" for plat, st, cnt in plat_stats]

    date_str = now.strftime("%Y-%m-%d")
    text = (
        f"<b>📊 SNS 일일 리포트 — {date_str}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📝 생성: {created}건\n"
        f"✅ 승인: {approved}건\n"
        f"🚀 발행: {published}건\n"
        f"❌ 실패: {failed}건\n"
        f"⏳ 대기: {pending}건\n"
        f"🚫 거절: {rejected}건\n"
    )

    if type_lines:
        text += f"\n<b>콘텐츠 타입별:</b>\n" + "\n".join(type_lines) + "\n"

    if plat_lines:
        text += f"\n<b>플랫폼별 발행:</b>\n" + "\n".join(plat_lines) + "\n"

    text += f"\n⏰ {now.strftime('%H:%M UTC')}"

    sent = await _send_telegram(text)
    logger.info("일일 SNS 리포트: created=%d, published=%d, sent=%s", created, published, sent)
    return {
        "created": created,
        "approved": approved,
        "published": published,
        "failed": failed,
        "pending": pending,
        "sent": sent,
    }


async def send_weekly_ops_report(db: AsyncSession) -> dict:
    """주간 SNS 운영 리포트 생성 + Telegram 전송."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    iso_cal = now.isocalendar()

    # 주간 총계
    total_created = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.created_at >= week_start)
    )).scalar() or 0

    total_published = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "published", SocialPost.published_at >= week_start)
    )).scalar() or 0

    total_failed = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "failed", SocialPost.created_at >= week_start)
    )).scalar() or 0

    total_rejected = (await db.execute(
        select(func.count()).select_from(SocialPost)
        .where(SocialPost.status == "rejected", SocialPost.created_at >= week_start)
    )).scalar() or 0

    # 성공률
    success_rate = round(total_published / max(1, total_created) * 100, 1)

    # 콘텐츠 타입별 주간 통계
    type_stats = (await db.execute(
        select(SocialPost.content_type, SocialPost.status, func.count())
        .where(SocialPost.created_at >= week_start)
        .group_by(SocialPost.content_type, SocialPost.status)
    )).all()

    type_summary: dict[str, dict[str, int]] = {}
    for ct, st, cnt in type_stats:
        type_summary.setdefault(ct, {})
        type_summary[ct][st] = cnt

    type_lines = []
    for ct, statuses in type_summary.items():
        total = sum(statuses.values())
        pub = statuses.get("published", 0)
        type_lines.append(f"  • {ct}: {total}건 (발행 {pub})")

    # 플랫폼별 주간 통계
    plat_stats = (await db.execute(
        select(
            SocialPostPlatform.platform,
            SocialPostPlatform.status,
            func.count(),
        )
        .where(SocialPostPlatform.published_at >= week_start)
        .group_by(SocialPostPlatform.platform, SocialPostPlatform.status)
    )).all()

    plat_summary: dict[str, dict[str, int]] = {}
    for plat, st, cnt in plat_stats:
        plat_summary.setdefault(plat, {})
        plat_summary[plat][st] = cnt

    plat_lines = []
    for plat, statuses in plat_summary.items():
        pub = statuses.get("published", 0)
        fail = statuses.get("failed", 0)
        plat_lines.append(f"  • {plat}: ✅ {pub} / ❌ {fail}")

    # 일별 발행 추이
    daily_stats = (await db.execute(
        select(
            func.date_trunc("day", SocialPost.created_at).label("day"),
            func.count(),
        )
        .where(SocialPost.created_at >= week_start)
        .group_by("day")
        .order_by("day")
    )).all()
    daily_lines = [f"  {d.strftime('%m/%d')}: {cnt}건" for d, cnt in daily_stats]

    week_label = f"{iso_cal.year}-W{iso_cal.week:02d}"
    text = (
        f"<b>📊 SNS 주간 리포트 — {week_label}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📝 총 생성: {total_created}건\n"
        f"🚀 총 발행: {total_published}건\n"
        f"❌ 총 실패: {total_failed}건\n"
        f"🚫 총 거절: {total_rejected}건\n"
        f"📈 성공률: {success_rate}%\n"
    )

    if type_lines:
        text += f"\n<b>콘텐츠 타입별:</b>\n" + "\n".join(type_lines) + "\n"

    if plat_lines:
        text += f"\n<b>플랫폼별:</b>\n" + "\n".join(plat_lines) + "\n"

    if daily_lines:
        text += f"\n<b>일별 추이:</b>\n" + "\n".join(daily_lines) + "\n"

    text += f"\n⏰ {now.strftime('%Y-%m-%d %H:%M UTC')}"

    sent = await _send_telegram(text)
    logger.info(
        "주간 SNS 리포트: created=%d, published=%d, rate=%.1f%%, sent=%s",
        total_created, total_published, success_rate, sent,
    )
    return {
        "total_created": total_created,
        "total_published": total_published,
        "total_failed": total_failed,
        "success_rate": success_rate,
        "sent": sent,
    }
