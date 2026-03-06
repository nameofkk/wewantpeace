"""SNS 콘텐츠 생성기 — Daily Movers / Spike Alert / Weekly Recap (ko+en)."""
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.spike_event import SpikeEvent
from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# 국가코드 → 해시태그 매핑
_COUNTRY_HASHTAGS: dict[str, str] = {
    "UA": "#Ukraine", "RU": "#Russia", "IL": "#Israel", "PS": "#Palestine",
    "IR": "#Iran", "CN": "#China", "TW": "#Taiwan", "KP": "#NorthKorea",
    "KR": "#SouthKorea", "US": "#USA", "SY": "#Syria", "YE": "#Yemen",
    "MM": "#Myanmar", "SD": "#Sudan", "ET": "#Ethiopia", "AF": "#Afghanistan",
    "IQ": "#Iraq", "LB": "#Lebanon", "PK": "#Pakistan", "IN": "#India",
    "JP": "#Japan", "TR": "#Turkey", "EG": "#Egypt", "SA": "#SaudiArabia",
    "NG": "#Nigeria", "CD": "#Congo", "SO": "#Somalia", "LY": "#Libya",
}


def _risk_from_severity(severity: int) -> str:
    if severity < 40:
        return "low"
    if severity < 70:
        return "medium"
    return "high"


def _build_hashtags(country_codes: list[str]) -> list[str]:
    tags = ["#WeWantPeace"]
    for cc in country_codes:
        tag = _COUNTRY_HASHTAGS.get(cc)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _call_openai(system_prompt: str, user_prompt: str) -> str | None:
    if not _OPENAI_KEY:
        logger.warning("OPENAI_API_KEY 미설정, AI 생성 건너뜀")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=_OPENAI_KEY, timeout=15.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("OpenAI 호출 실패")
        return None


async def _generate_card_for_post(post: SocialPost, cluster=None):
    """포스트에 카드 이미지 생성 + 업로드 (실패해도 무시)."""
    try:
        from worker.social.card_generator import generate_and_upload_card
        await generate_and_upload_card(post, cluster)
    except Exception:
        logger.warning("카드 이미지 생성 실패 (무시): post=%s", post.id)


# ── Daily Movers ─────────────────────────────────────────────────────────────

_DAILY_SYSTEM_KO = (
    "You are a concise news writer for social media about global conflicts. "
    "Write a Korean post (under 280 characters) summarizing the top 3 global issues. "
    "Be factual, neutral, and informative. Do NOT include hashtags."
)

_DAILY_SYSTEM_EN = (
    "You are a concise news writer for social media about global conflicts. "
    "Write an English post (under 280 characters) summarizing the top 3 global issues. "
    "Be factual, neutral, and informative. Do NOT include hashtags."
)


async def generate_daily_movers(db: AsyncSession) -> list[SocialPost]:
    """지난 24시간 severity 상위 3개 클러스터로 Daily Movers 포스트 생성 (ko+en)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posts = []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.severity > 0,
            IssueCluster.last_event_at >= cutoff,
        )
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(3)
    )
    top_clusters = result.scalars().all()

    if not top_clusters:
        logger.info("Daily Movers: 최근 24시간 클러스터 없음")
        return posts

    # 공통 데이터 준비
    items_ko, items_en = [], []
    country_codes = []
    max_severity = 0
    for i, c in enumerate(top_clusters, 1):
        items_ko.append(f"{i}. [{c.country_code or '??'}] {c.title_ko or c.title} (severity: {c.severity})")
        items_en.append(f"{i}. [{c.country_code or '??'}] {c.title} (severity: {c.severity})")
        if c.country_code:
            country_codes.append(c.country_code)
        max_severity = max(max_severity, c.severity)

    hashtags = _build_hashtags(country_codes)
    risk = _risk_from_severity(max_severity)

    # ko + en 포스트 생성
    for lang, system_prompt, items, fallback_prefix in [
        ("ko", _DAILY_SYSTEM_KO, items_ko, "오늘의 주요 이슈"),
        ("en", _DAILY_SYSTEM_EN, items_en, "Today's Top Issues"),
    ]:
        dedup_key = f"daily_movers:{lang}:{today}"

        existing = await db.execute(
            select(SocialPost).where(SocialPost.dedup_key == dedup_key)
        )
        if existing.scalar_one_or_none():
            logger.info("Daily Movers 이미 존재: %s", dedup_key)
            continue

        prompt_prefix = "다음 이슈를 요약하여 SNS 포스트를 작성하세요:" if lang == "ko" else "Summarize these issues into a social media post:"
        user_prompt = prompt_prefix + "\n" + "\n".join(items)
        body = _call_openai(system_prompt, user_prompt)

        if not body:
            lines = [f"- {c.title_ko or c.title}" if lang == "ko" else f"- {c.title}" for c in top_clusters]
            body = f"{fallback_prefix}\n\n" + "\n".join(lines)

        if len(body) > 280:
            body = body[:277] + "..."

        post = SocialPost(
            content_type="daily_movers",
            lang=lang,
            body_text=body,
            hashtags=hashtags,
            risk_level=risk,
            source_cluster_id=top_clusters[0].id,
            dedup_key=dedup_key,
            status="pending_review",
        )
        db.add(post)
        await db.flush()
        await _generate_card_for_post(post, top_clusters[0])
        posts.append(post)
        logger.info("Daily Movers [%s] 생성: %s (risk=%s)", lang, post.id, risk)

    return posts


# ── Spike Alert ──────────────────────────────────────────────────────────────

_SPIKE_SYSTEM_KO = (
    "You are a breaking news writer for social media about global conflicts. "
    "Write an urgent-style Korean post (under 280 characters) about this spike event. "
    "Be factual and concise. Do NOT include hashtags."
)

_SPIKE_SYSTEM_EN = (
    "You are a breaking news writer for social media about global conflicts. "
    "Write an urgent-style English post (under 280 characters) about this spike event. "
    "Be factual and concise. Do NOT include hashtags."
)


async def generate_spike_alert(
    spike: SpikeEvent,
    cluster: IssueCluster,
    db: AsyncSession,
) -> list[SocialPost]:
    """스파이크 이벤트 기반 긴급 포스트 생성 (ko+en)."""
    posts = []
    country_codes = [cluster.country_code] if cluster.country_code else []
    hashtags = _build_hashtags(country_codes)
    risk = "high" if cluster.severity >= 70 else "medium"

    for lang, system_prompt, fallback_tmpl in [
        ("ko", _SPIKE_SYSTEM_KO, "[속보] {title} (심각도: {sev})"),
        ("en", _SPIKE_SYSTEM_EN, "[BREAKING] {title} (Severity: {sev})"),
    ]:
        dedup_key = f"spike_alert:{lang}:{spike.id}"

        existing = await db.execute(
            select(SocialPost).where(SocialPost.dedup_key == dedup_key)
        )
        if existing.scalar_one_or_none():
            logger.info("Spike Alert 이미 존재: %s", dedup_key)
            continue

        title = (cluster.title_ko or cluster.title) if lang == "ko" else cluster.title
        country_label = cluster.country_code or ("미상" if lang == "ko" else "Unknown")

        if lang == "ko":
            user_prompt = (
                f"긴급 속보:\n"
                f"제목: {title}\n"
                f"국가: {country_label}\n"
                f"심각도: {cluster.severity}/100\n"
                f"KScore: {cluster.kscore:.1f}"
            )
        else:
            user_prompt = (
                f"Breaking news:\n"
                f"Title: {title}\n"
                f"Country: {country_label}\n"
                f"Severity: {cluster.severity}/100\n"
                f"KScore: {cluster.kscore:.1f}"
            )

        body = _call_openai(system_prompt, user_prompt)
        if not body:
            body = fallback_tmpl.format(title=title, sev=cluster.severity)

        if len(body) > 280:
            body = body[:277] + "..."

        post = SocialPost(
            content_type="spike_alert",
            lang=lang,
            body_text=body,
            hashtags=hashtags,
            risk_level=risk,
            source_cluster_id=cluster.id,
            source_spike_id=spike.id,
            dedup_key=dedup_key,
            status="pending_review",
        )
        db.add(post)
        await db.flush()
        await _generate_card_for_post(post, cluster)
        posts.append(post)
        logger.info("Spike Alert [%s] 생성: %s (risk=%s)", lang, post.id, risk)

    return posts


# ── Weekly Recap ─────────────────────────────────────────────────────────────

_WEEKLY_SYSTEM_KO = (
    "You are a weekly news summarizer for social media about global conflicts. "
    "Write a Korean weekly recap post (under 280 characters) summarizing the week's key events. "
    "Be informative and neutral. Do NOT include hashtags."
)

_WEEKLY_SYSTEM_EN = (
    "You are a weekly news summarizer for social media about global conflicts. "
    "Write an English weekly recap post (under 280 characters) summarizing the week's key events. "
    "Be informative and neutral. Do NOT include hashtags."
)


async def generate_weekly_recap(db: AsyncSession) -> list[SocialPost]:
    """지난 7일 클러스터 통계 기반 주간 요약 포스트 생성 (ko+en)."""
    now = datetime.now(timezone.utc)
    iso_cal = now.isocalendar()
    posts = []

    cutoff = now - timedelta(days=7)

    # 국가별 통계
    stats_result = await db.execute(
        select(
            IssueCluster.country_code,
            func.count().label("event_count"),
            func.avg(IssueCluster.severity).label("avg_severity"),
        )
        .where(
            IssueCluster.severity > 0,
            IssueCluster.last_event_at >= cutoff,
            IssueCluster.country_code.isnot(None),
        )
        .group_by(IssueCluster.country_code)
        .order_by(func.avg(IssueCluster.severity).desc())
        .limit(10)
    )
    country_stats = stats_result.all()

    if not country_stats:
        logger.info("Weekly Recap: 지난 7일 데이터 없음")
        return posts

    total_result = await db.execute(
        select(func.count())
        .select_from(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
    )
    total_clusters = total_result.scalar() or 0

    country_codes = [s.country_code for s in country_stats[:5] if s.country_code]
    hashtags = _build_hashtags(country_codes)

    for lang, system_prompt in [
        ("ko", _WEEKLY_SYSTEM_KO),
        ("en", _WEEKLY_SYSTEM_EN),
    ]:
        dedup_key = f"weekly_recap:{lang}:{iso_cal.year}-W{iso_cal.week:02d}"

        existing = await db.execute(
            select(SocialPost).where(SocialPost.dedup_key == dedup_key)
        )
        if existing.scalar_one_or_none():
            logger.info("Weekly Recap 이미 존재: %s", dedup_key)
            continue

        stats_text = []
        for s in country_stats[:5]:
            if lang == "ko":
                stats_text.append(f"- {s.country_code}: {s.event_count}건, 평균 심각도 {s.avg_severity:.0f}")
            else:
                stats_text.append(f"- {s.country_code}: {s.event_count} events, avg severity {s.avg_severity:.0f}")

        if lang == "ko":
            user_prompt = (
                f"지난 7일 글로벌 이슈 통계:\n"
                f"총 {total_clusters}개 이슈 클러스터\n"
                f"주요 국가:\n" + "\n".join(stats_text)
            )
            fallback = f"이번 주 글로벌 이슈 요약: {total_clusters}개 이슈, 상위 국가 {', '.join(country_codes[:3])}"
        else:
            user_prompt = (
                f"Global issues stats (past 7 days):\n"
                f"Total {total_clusters} issue clusters\n"
                f"Top countries:\n" + "\n".join(stats_text)
            )
            fallback = f"This week: {total_clusters} issues. Top: {', '.join(country_codes[:3])}"

        body = _call_openai(system_prompt, user_prompt)
        if not body:
            body = fallback

        if len(body) > 280:
            body = body[:277] + "..."

        post = SocialPost(
            content_type="weekly_recap",
            lang=lang,
            body_text=body,
            hashtags=hashtags,
            risk_level="low",
            dedup_key=dedup_key,
            status="pending_review",
        )
        db.add(post)
        await db.flush()
        await _generate_card_for_post(post)
        posts.append(post)
        logger.info("Weekly Recap [%s] 생성: %s", lang, post.id)

    return posts
