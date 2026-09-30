"""SNS 콘텐츠 생성기 — Daily brief / 단건 브리프 / Week in review (영어, Threads)."""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

# ── 공통 ────────────────────────────────────────────────────────────────────
# 2026-09-30 개편: 한·영 혼합 + 이모지 + BREAKING 톤 → 영어 정보형 브리프.
# 본문·카드·출처 댓글 조립은 worker/social/brief.py, 카드 서식은 brief_card.py.

def _initial_status() -> str:
    """새 형식 첫 이틀은 텔레그램 승인을 거친다 (SOCIAL_REVIEW_UNTIL)."""
    from worker.social.config import review_required
    return "pending_review" if review_required() else "approved"


async def notify_pending(posts) -> None:
    """승인 대기 게시물을 텔레그램 승인 봇에 올린다. DB 커밋 뒤에 불러야 버튼이 동작한다."""
    from worker.social.telegram_bot import send_review_message
    for post in posts:
        if post is not None and post.status == "pending_review":
            try:
                await send_review_message(post)
            except Exception:
                logger.exception("승인 요청 전송 실패: post=%s", post.id)


async def _in_thread(fn, *args, **kwargs):
    import asyncio
    import functools
    return await asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *args, **kwargs))


async def _already_exists(db: AsyncSession, dedup_key: str) -> bool:
    existing = await db.execute(select(SocialPost.id).where(SocialPost.dedup_key == dedup_key))
    return existing.scalar_one_or_none() is not None


# ── Daily brief ──────────────────────────────────────────────────────────────

async def generate_daily_movers(db: AsyncSession) -> SocialPost | None:
    """지난 24시간 주요 이슈 3개(나라 중복 없이, 출처 2곳 이상)를 일간 브리프로."""
    from worker.social import brief as B
    from worker.social.brief_card import list_slides, attach_carousel

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedup_key = f"daily_movers:{today}"
    if await _already_exists(db, dedup_key):
        logger.info("Daily brief 이미 존재: %s", dedup_key)
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,  # noqa: E712
            IssueCluster.severity > 0,
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.country_code.isnot(None),
        )
        .order_by(IssueCluster.kscore.desc(), IssueCluster.severity.desc())
        .limit(30)
    )
    picked: list[tuple[IssueCluster, dict]] = []
    seen_countries: set[str] = set()
    for c in result.scalars().all():
        if c.country_code in seen_countries or B.is_template_title(c):
            continue
        ctx = await B.gather_context(db, c, hours=24)
        if ctx["n_sources"] < 2:
            continue
        picked.append((c, ctx))
        seen_countries.add(c.country_code)
        if len(picked) == 3:
            break

    if len(picked) < 2:
        logger.info("Daily brief: 조건을 채우는 이슈가 2개 미만 — 건너뜀")
        return None

    head = "Three developments from the last 24 hours:" if len(picked) == 3 else "Key developments from the last 24 hours:"
    lines, items = [], []
    for i, (c, ctx) in enumerate(picked, 1):
        title = B._fit(B._clean(c.title), 110)
        name = B.country_name(c.country_code)
        lines.append(f"{i}. {name}: {title}")
        items.append({"country": name, "headline": title, "meta": f"{ctx['n_sources']} sources",
                      "photos": ctx.get("photos") or []})
    body = "\n\n".join([head, "\n".join(lines)])[: B.THREADS_LIMIT]
    countries = " · ".join(it["country"] for it in items)

    post = SocialPost(
        content_type="daily_movers",
        lang="en",
        body_text=body,
        reply_text=f"Full timelines for each story: {B.SITE}/?ref=threads\n\n"
                   f"A weekly brief by email: {B.SITE}/brief?ref=threads",
        hashtags=["Geopolitics"],
        risk_level="low",
        source_cluster_id=picked[0][0].id,
        dedup_key=dedup_key,
        status=_initial_status(),
    )
    db.add(post)
    await db.flush()
    slides = await _in_thread(list_slides, title=f"{len(items)} stories from the last 24 hours",
                              dek=countries, kicker=datetime.now(timezone.utc).strftime("Daily brief · %b %d"),
                              items=items)
    await attach_carousel(post, slides)
    logger.info("Daily brief 생성: %s (%d건, status=%s)", post.id, len(items), post.status)
    return post


# ── KScore alert → 단건 브리프 ────────────────────────────────────────────────

async def generate_kscore_alert(
    cluster: IssueCluster,
    db: AsyncSession,
    ctx: dict | None = None,
) -> SocialPost | None:
    """이슈 하나를 "무슨 일 / 왜 중요 / 지켜볼 점" 브리프로. 품질 게이트를 못 넘으면 None."""
    from worker.social import brief as B
    from worker.social.brief_card import alert_slides, attach_carousel
    from worker.social.config import SOCIAL_MIN_SOURCES

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedup_key = f"kscore_alert:{cluster.id}:{today}"
    if await _already_exists(db, dedup_key):
        logger.info("KScore brief 이미 존재: %s", dedup_key)
        return None

    ctx = ctx or await B.gather_context(db, cluster)
    reason = B.quality_reject_reason(cluster, ctx, SOCIAL_MIN_SOURCES)
    if reason:
        logger.info("KScore brief 품질 게이트 탈락: cluster=%s reason=%s", cluster.id, reason)
        return None

    if B.recently_skipped(cluster.id):
        return None
    brief = B.build_brief(cluster, ctx)
    if not brief:
        # 예전엔 이모지 템플릿으로라도 내보냈다 — 이제는 안 내보낸다
        logger.info("KScore brief 없음(AI 판단 skip 또는 실패) → 게시 안 함: cluster=%s", cluster.id)
        B.remember_skip(cluster.id)
        return None

    post = SocialPost(
        content_type="kscore_alert",
        lang="en",
        body_text=B.compose_alert_text(brief, ctx["n_sources"], cluster.id, ctx["source_names"]),
        reply_text=B.compose_sources_reply(ctx["source_names"], cluster.country_code,
                                           brief.get("watch"), cluster.id),
        hashtags=[B.topic_tag_for(cluster.country_code, cluster.topic)],
        risk_level="high" if cluster.severity >= 70 else "medium",
        source_cluster_id=cluster.id,
        dedup_key=dedup_key,
        status=_initial_status(),
    )
    db.add(post)
    await db.flush()
    # 기사 사진 받기가 동기 네트워크 작업이라 이벤트 루프 밖에서 장을 만든다
    slides = await _in_thread(alert_slides, brief, country=B.country_name(cluster.country_code),
                              cc=cluster.country_code or "", n_sources=ctx["n_sources"],
                              source_names=ctx["source_names"], photos=ctx.get("photos") or [],
                              when=ctx.get("newest_event_at"))
    await attach_carousel(post, slides)
    logger.info("KScore brief 생성: %s (sources=%d, slides=%d, status=%s)",
                post.id, ctx["n_sources"], len(post.image_urls or []), post.status)
    return post


# 하위호환 alias
async def generate_spike_alert(spike, cluster, db):
    """Deprecated: use generate_kscore_alert instead."""
    return await generate_kscore_alert(cluster, db)


# ── Week in review ───────────────────────────────────────────────────────────

async def generate_weekly_recap(db: AsyncSession) -> SocialPost | None:
    """지난 7일 이슈가 가장 많았던 나라 4곳과 나라별 대표 이슈."""
    from worker.social import brief as B
    from worker.social.brief_card import list_slides, attach_carousel

    now = datetime.now(timezone.utc)
    iso_cal = now.isocalendar()
    dedup_key = f"weekly_recap:{iso_cal.year}-W{iso_cal.week:02d}"
    if await _already_exists(db, dedup_key):
        logger.info("Weekly recap 이미 존재: %s", dedup_key)
        return None

    cutoff = now - timedelta(days=7)
    stats = (await db.execute(
        select(IssueCluster.country_code, func.count().label("n"))
        .where(
            IssueCluster.severity >= 40,
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.country_code.isnot(None),
        )
        .group_by(IssueCluster.country_code)
        .order_by(func.count().desc())
        .limit(8)
    )).all()

    items, lines = [], []
    for row in stats:
        candidates = (await db.execute(
            select(IssueCluster)
            .where(
                IssueCluster.country_code == row.country_code,
                IssueCluster.last_event_at >= cutoff,
            )
            .order_by(IssueCluster.event_count.desc(), IssueCluster.kscore.desc())
            .limit(5)
        )).scalars().all()
        top = next((c for c in candidates if not B.is_template_title(c)), None)
        if not top:
            continue
        name = B.country_name(row.country_code)
        title = B._fit(B._clean(top.title), 100)
        ctx = await B.gather_context(db, top, hours=24 * 7)
        items.append({"country": name, "headline": title, "meta": f"{row.n} issues tracked",
                      "photos": ctx.get("photos") or []})
        lines.append(f"{name} ({row.n} issues): {title}")
        if len(items) == 4:
            break

    if len(items) < 2:
        logger.info("Weekly recap: 데이터 부족 — 건너뜀")
        return None

    start = (now - timedelta(days=7)).strftime("%b %d")
    end = now.strftime("%b %d")
    head = f"Week in review, {start} to {end}. Where the most activity was:"
    body = "\n\n".join([head, "\n".join(lines)])
    while len(body) > B.THREADS_LIMIT and len(lines) > 2:
        lines.pop()
        body = "\n\n".join([head, "\n".join(lines)])

    post = SocialPost(
        content_type="weekly_recap",
        lang="en",
        body_text=body[: B.THREADS_LIMIT],
        reply_text=f"Country timelines: {B.SITE}/?ref=threads\n\n"
                   f"A weekly brief by email: {B.SITE}/brief?ref=threads",
        hashtags=["Geopolitics"],
        risk_level="low",
        dedup_key=dedup_key,
        status=_initial_status(),
    )
    db.add(post)
    await db.flush()
    slides = await _in_thread(list_slides, title="The week in conflict", dek=f"{start} to {end}",
                              kicker="Week in review", items=items)
    await attach_carousel(post, slides)
    logger.info("Weekly recap 생성: %s (status=%s)", post.id, post.status)
    return post
