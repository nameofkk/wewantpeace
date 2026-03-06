"""SNS 콘텐츠 생성기 — Daily Movers / Spike Alert / Weekly Recap."""
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


# ── Daily Movers ─────────────────────────────────────────────────────────────

_DAILY_SYSTEM = (
    "You are a concise news writer for social media about global conflicts. "
    "Write a Korean post (under 280 characters) summarizing the top 3 global issues. "
    "Be factual, neutral, and informative. Do NOT include hashtags."
)


async def generate_daily_movers(db: AsyncSession) -> SocialPost | None:
    """지난 24시간 severity 상위 3개 클러스터로 Daily Movers 포스트 생성."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedup_key = f"daily_movers:ko:{today}"

    # 중복 체크
    existing = await db.execute(
        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none():
        logger.info("Daily Movers 이미 존재: %s", dedup_key)
        return None

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
        return None

    # AI 프롬프트 구성
    items = []
    country_codes = []
    max_severity = 0
    for i, c in enumerate(top_clusters, 1):
        items.append(f"{i}. [{c.country_code or '??'}] {c.title_ko or c.title} (severity: {c.severity})")
        if c.country_code:
            country_codes.append(c.country_code)
        max_severity = max(max_severity, c.severity)

    user_prompt = "다음 이슈를 요약하여 SNS 포스트를 작성하세요:\n" + "\n".join(items)
    body = _call_openai(_DAILY_SYSTEM, user_prompt)

    if not body:
        # AI 실패 시 기본 포맷
        lines = []
        for c in top_clusters:
            flag = f":flag-{(c.country_code or 'UN').lower()}:" if c.country_code else ""
            lines.append(f"{flag} {c.title_ko or c.title}")
        body = "오늘의 주요 이슈\n\n" + "\n".join(lines)

    # 280자 초과 시 자르기
    if len(body) > 280:
        body = body[:277] + "..."

    hashtags = _build_hashtags(country_codes)
    risk = _risk_from_severity(max_severity)

    post = SocialPost(
        content_type="daily_movers",
        lang="ko",
        body_text=body,
        hashtags=hashtags,
        risk_level=risk,
        source_cluster_id=top_clusters[0].id,
        dedup_key=dedup_key,
        status="pending_review",
    )
    db.add(post)
    await db.flush()
    logger.info("Daily Movers 생성: %s (risk=%s)", post.id, risk)
    return post


# ── Spike Alert ──────────────────────────────────────────────────────────────

_SPIKE_SYSTEM = (
    "You are a breaking news writer for social media about global conflicts. "
    "Write an urgent-style Korean post (under 280 characters) about this spike event. "
    "Be factual and concise. Do NOT include hashtags."
)


async def generate_spike_alert(
    spike: SpikeEvent,
    cluster: IssueCluster,
    db: AsyncSession,
) -> SocialPost | None:
    """스파이크 이벤트 기반 긴급 포스트 생성."""
    dedup_key = f"spike_alert:{spike.id}"

    existing = await db.execute(
        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none():
        logger.info("Spike Alert 이미 존재: %s", dedup_key)
        return None

    user_prompt = (
        f"긴급 속보:\n"
        f"제목: {cluster.title_ko or cluster.title}\n"
        f"국가: {cluster.country_code or '미상'}\n"
        f"심각도: {cluster.severity}/100\n"
        f"KScore: {cluster.kscore:.1f}"
    )
    body = _call_openai(_SPIKE_SYSTEM, user_prompt)

    if not body:
        body = f"[속보] {cluster.title_ko or cluster.title} (심각도: {cluster.severity})"

    if len(body) > 280:
        body = body[:277] + "..."

    country_codes = [cluster.country_code] if cluster.country_code else []
    hashtags = _build_hashtags(country_codes)
    risk = "high" if cluster.severity >= 70 else "medium"

    post = SocialPost(
        content_type="spike_alert",
        lang="ko",
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
    logger.info("Spike Alert 생성: %s (risk=%s)", post.id, risk)
    return post


# ── Weekly Recap ─────────────────────────────────────────────────────────────

_WEEKLY_SYSTEM = (
    "You are a weekly news summarizer for social media about global conflicts. "
    "Write a Korean weekly recap post (under 280 characters) summarizing the week's key events. "
    "Be informative and neutral. Do NOT include hashtags."
)


async def generate_weekly_recap(db: AsyncSession) -> SocialPost | None:
    """지난 7일 클러스터 통계 기반 주간 요약 포스트 생성."""
    now = datetime.now(timezone.utc)
    iso_cal = now.isocalendar()
    dedup_key = f"weekly_recap:ko:{iso_cal.year}-W{iso_cal.week:02d}"

    existing = await db.execute(
        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none():
        logger.info("Weekly Recap 이미 존재: %s", dedup_key)
        return None

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
        return None

    # 전체 클러스터 수
    total_result = await db.execute(
        select(func.count())
        .select_from(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
    )
    total_clusters = total_result.scalar() or 0

    # AI 프롬프트
    stats_text = []
    country_codes = []
    for s in country_stats[:5]:
        stats_text.append(f"- {s.country_code}: {s.event_count}건, 평균 심각도 {s.avg_severity:.0f}")
        if s.country_code:
            country_codes.append(s.country_code)

    user_prompt = (
        f"지난 7일 글로벌 이슈 통계:\n"
        f"총 {total_clusters}개 이슈 클러스터\n"
        f"주요 국가:\n" + "\n".join(stats_text)
    )
    body = _call_openai(_WEEKLY_SYSTEM, user_prompt)

    if not body:
        body = f"이번 주 글로벌 이슈 요약: {total_clusters}개 이슈, 상위 국가 {', '.join(country_codes[:3])}"

    if len(body) > 280:
        body = body[:277] + "..."

    hashtags = _build_hashtags(country_codes)

    post = SocialPost(
        content_type="weekly_recap",
        lang="ko",
        body_text=body,
        hashtags=hashtags,
        risk_level="low",
        dedup_key=dedup_key,
        status="pending_review",
    )
    db.add(post)
    await db.flush()
    logger.info("Weekly Recap 생성: %s", post.id)
    return post
