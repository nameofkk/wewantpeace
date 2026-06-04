"""SNS 콘텐츠 생성기 — Daily Movers / KScore Alert / Weekly Recap (bilingual)."""
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.social_post import SocialPost

logger = logging.getLogger(__name__)

from worker.ai_config import get_client as _get_ai_client, get_model as _get_ai_model, is_available as _ai_available

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


def _clean_markdown(text: str) -> str:
    """AI 응답에서 마크다운 포맷 제거 (DB 저장 전 정규화).

    **bold** → bold, *italic* → text, __underline__ → text, _italic_ → text
    """
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    return text


def _risk_from_severity(severity: int) -> str:
    if severity < 40:
        return "low"
    if severity < 70:
        return "medium"
    return "high"


# v7: 토픽→해시태그 매핑
_TOPIC_HASHTAGS: dict[str, list[str]] = {
    "conflict": ["#Breaking", "#Conflict"],
    "terror": ["#Breaking", "#Terror"],
    "coup": ["#Breaking", "#Coup"],
    "sanctions": ["#Sanctions", "#Geopolitics"],
    "cyber": ["#CyberAttack", "#CyberSecurity"],
    "protest": ["#Protest", "#Unrest"],
    "diplomacy": ["#Diplomacy", "#Peace"],
    "maritime": ["#Maritime", "#Security"],
    "disaster": ["#Disaster", "#HumanitarianCrisis"],
    "health": ["#HealthCrisis", "#Global"],
}


def _build_hashtags(country_codes: list[str], topic: str = "") -> list[str]:
    """v7: 동적 토픽+국가 기반 해시태그 (고정 #WeWantPeace 제거)."""
    tags: list[str] = []
    # 토픽 기반 해시태그
    topic_tags = _TOPIC_HASHTAGS.get(topic, [])
    for t in topic_tags:
        if t not in tags:
            tags.append(t)
    # 국가 기반 해시태그
    for cc in country_codes:
        tag = _COUNTRY_HASHTAGS.get(cc)
        if tag and tag not in tags:
            tags.append(tag)
    # 최대 3개로 제한
    return tags[:3] if tags else ["#WeWantPeace"]


def _call_openai(system_prompt: str, user_prompt: str) -> str | None:
    if not _ai_available():
        logger.warning("AI API 키 미설정, AI 생성 건너뜀")
        return None
    try:
        client = _get_ai_client(timeout=15.0)
        resp = client.chat.completions.create(
            model=_get_ai_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("AI 호출 실패")
        return None


async def _generate_card_for_post(
    post: SocialPost,
    clusters=None,
):
    """포스트에 카드 이미지 생성 (실패 시 기본 OG 이미지 폴백)."""
    try:
        from worker.social.card_generator import generate_card_for_post
        await generate_card_for_post(post, clusters)
    except Exception:
        logger.warning("카드 이미지 생성 실패 (무시): post=%s", post.id)

    # 카드 이미지 생성 실패 시 기본 OG 이미지를 폴백으로 설정
    if not post.image_url:
        post.image_url = "https://www.wewantpeace.live/og-default.png"


# ── 공통 bilingual 시스템 프롬프트 ──────────────────────────────────────────

_BILINGUAL_SYSTEM = (
    "You write punchy, scroll-stopping bilingual social media posts about global conflicts "
    "for WeWantPeace — a real-time conflict monitoring platform (Threads & Telegram).\n"
    "Format — English first, blank line, Korean, blank line, CTA:\n"
    "\n"
    "[emoji] Headline in English\n"
    "Key point 1 · Key point 2\n"
    "\n"
    "[emoji] 한국어 헤드라인\n"
    "핵심 1 · 핵심 2\n"
    "\n"
    "→ Track live updates · 실시간 분석 확인\n"
    "www.wewantpeace.live\n"
    "\n"
    "Rules:\n"
    "- Body MUST be under 380 chars total (EN + KO combined)\n"
    "- Use 1-2 relevant emojis (🔴⚡🌍🚨 etc.) for visual punch\n"
    "- Use · or | as separators, NOT full sentences\n"
    "- Be factual but impactful — hook the reader in 2 seconds\n"
    "- Use line breaks for scannable layout\n"
    "- End with a bilingual CTA line + site URL as shown above\n"
    "- NO hashtags (added separately), NO labels like 'EN:'/'KO:'\n"
    "- Korean text must be pure Korean (한국어만). No Russian, Chinese, or other languages mixed in.\n"
    "- Include specific facts: country name, numbers, actions — avoid vague phrases\n"
    "- NO markdown formatting: no **bold**, no *italic*, no _underline_, no __text__\n"
    "- Plain text only — no special characters for formatting\n"
    "- NEVER speculate or fabricate details not present in the provided data — if a specific fact is absent, omit it rather than guess"
)

_SPIKE_BILINGUAL_SYSTEM = (
    "You write URGENT breaking news bilingual posts about global conflicts "
    "for WeWantPeace — a real-time conflict monitoring platform (Threads & Telegram).\n"
    "Format — English first, blank line, Korean, blank line, CTA:\n"
    "\n"
    "🚨 [BREAKING] Headline\n"
    "Key detail · Impact\n"
    "\n"
    "🚨 [속보] 헤드라인\n"
    "핵심 · 영향\n"
    "\n"
    "🔗 Full analysis · 상세 분석\n"
    "www.wewantpeace.live\n"
    "\n"
    "Rules:\n"
    "- Body MUST be under 380 chars total (EN + KO combined)\n"
    "- Start with 🚨 for urgency\n"
    "- Use · or | as separators\n"
    "- Maximum impact in minimum words\n"
    "- End with bilingual CTA + URL as shown\n"
    "- NO hashtags, NO labels\n"
    "- Korean text must be pure Korean (한국어만). No Russian, Chinese, or other languages.\n"
    "- Include specific facts: numbers, locations, actors\n"
    "- NO markdown formatting: no **bold**, no *italic*, no _underline_, no __text__\n"
    "- Plain text only — no special characters for formatting\n"
    "- NEVER speculate or fabricate details not present in the provided data — if a specific fact is absent, omit it rather than guess"
)

_WEEKLY_BILINGUAL_SYSTEM = (
    "You write weekly recap bilingual posts about global conflicts "
    "for WeWantPeace — a real-time conflict monitoring platform (Threads & Telegram).\n"
    "Format — English first, blank line, Korean, blank line, CTA:\n"
    "\n"
    "📊 Week in Review: [headline]\n"
    "Top: Country1 · Country2 · Country3\n"
    "\n"
    "📊 주간 리뷰: [헤드라인]\n"
    "상위: 국가1 · 국가2 · 국가3\n"
    "\n"
    "📈 Dive deeper · 더 알아보기\n"
    "www.wewantpeace.live\n"
    "\n"
    "Rules:\n"
    "- Body MUST be under 380 chars total (EN + KO combined)\n"
    "- Highlight top 2-3 countries with stats\n"
    "- Use · or | as separators\n"
    "- Clean, scannable format\n"
    "- End with bilingual CTA + URL as shown\n"
    "- NO hashtags, NO labels\n"
    "- Korean text must be pure Korean (한국어만). No Russian, Chinese, or other languages.\n"
    "- Use specific numbers and country names\n"
    "- NO markdown formatting: no **bold**, no *italic*, no _underline_, no __text__\n"
    "- Plain text only — no special characters for formatting\n"
    "- NEVER speculate or fabricate details not present in the provided data — if a specific fact is absent, omit it rather than guess"
)


# ── Daily Movers ─────────────────────────────────────────────────────────────

async def generate_daily_movers(db: AsyncSession) -> SocialPost | None:
    """지난 24시간 severity 상위 3개 클러스터로 Daily Movers 포스트 생성 (bilingual)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedup_key = f"daily_movers:{today}"

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
            IssueCluster.country_code.isnot(None),
        )
        .order_by(IssueCluster.severity.desc(), IssueCluster.kscore.desc())
        .limit(3)
    )
    top_clusters = result.scalars().all()

    if not top_clusters:
        logger.info("Daily Movers: 최근 24시간 클러스터 없음")
        return None

    # 데이터 준비
    items = []
    country_codes = []
    max_severity = 0
    for i, c in enumerate(top_clusters, 1):
        title_bi = f"{c.title}"
        if c.title_ko and c.title_ko != c.title:
            title_bi = f"{c.title} / {c.title_ko}"
        items.append(f"{i}. [{c.country_code or '??'}] {title_bi} (severity: {c.severity})")
        if c.country_code:
            country_codes.append(c.country_code)
        max_severity = max(max_severity, c.severity)

    hashtags = _build_hashtags(country_codes, topic=top_clusters[0].topic or "")
    risk = _risk_from_severity(max_severity)

    user_prompt = "Summarize these top global issues:\n" + "\n".join(items)
    body = _call_openai(_BILINGUAL_SYSTEM, user_prompt)

    if not body:
        # 폴백: bilingual compact
        top = top_clusters[0]
        en_title = top.title[:60] if len(top.title) > 60 else top.title
        ko_title = (top.title_ko or top.title)[:60]
        body = f"🌍 {en_title}\n\n🌍 {ko_title}"

    body = _clean_markdown(body)
    body = body + f"\n\n⚠️ Severity {max_severity}/100"
    if len(body) > 500:
        body = body[:497] + "..."

    post = SocialPost(
        content_type="daily_movers",
        lang="bi",
        body_text=body,
        hashtags=hashtags,
        risk_level=risk,
        source_cluster_id=top_clusters[0].id,
        dedup_key=dedup_key,
        status="approved",
    )
    db.add(post)
    await db.flush()
    await _generate_card_for_post(post, top_clusters)
    logger.info("Daily Movers [bi] 생성: %s (risk=%s)", post.id, risk)
    return post


# ── KScore Alert (v7: Spike Alert 대체) ───────────────────────────────────

async def generate_kscore_alert(
    cluster: IssueCluster,
    db: AsyncSession,
) -> SocialPost | None:
    """v7: KScore 기반 긴급 포스트 생성 (SpikeEvent 파라미터 제거, bilingual)."""
    # cluster_id + 날짜 기반 dedup — 같은 클러스터는 하루 1회만 포스트
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedup_key = f"kscore_alert:{cluster.id}:{today}"

    existing = await db.execute(
        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none():
        logger.info("KScore Alert 이미 존재: %s", dedup_key)
        return None

    # 같은 클러스터의 최근 72시간 내 published 포스트가 있으면 중복 방지
    published_cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    published_check = await db.execute(
        select(SocialPost.id).where(
            SocialPost.source_cluster_id == cluster.id,
            SocialPost.content_type == "kscore_alert",
            SocialPost.status == "published",
            SocialPost.published_at >= published_cutoff,
        ).limit(1)
    )
    if published_check.scalar_one_or_none():
        logger.info("KScore Alert 72시간 내 이미 발행됨: cluster=%s", cluster.id)
        return None

    country_codes = [cluster.country_code] if cluster.country_code else []
    hashtags = _build_hashtags(country_codes, topic=cluster.topic or "")
    risk = "high" if cluster.severity >= 70 else "medium"

    title_en = cluster.title
    title_ko = cluster.title_ko or cluster.title
    country_label = cluster.country_code or "Unknown"

    user_prompt = (
        f"Breaking news:\n"
        f"Title (EN): {title_en}\n"
        f"Title (KO): {title_ko}\n"
        f"Country: {country_label}\n"
        f"Severity: {cluster.severity}/100\n"
        f"KScore: {cluster.kscore:.1f}"
    )

    body = _call_openai(_SPIKE_BILINGUAL_SYSTEM, user_prompt)
    if not body:
        body = f"🚨 {title_en}\n\n🚨 {title_ko}"

    body = _clean_markdown(body)
    body = body + f"\n\n⚠️ Severity {cluster.severity}/100"
    if len(body) > 500:
        body = body[:497] + "..."

    post = SocialPost(
        content_type="kscore_alert",
        lang="bi",
        body_text=body,
        hashtags=hashtags,
        risk_level=risk,
        source_cluster_id=cluster.id,
        dedup_key=dedup_key,
        status="approved",
    )
    db.add(post)
    await db.flush()
    await _generate_card_for_post(post, [cluster])
    logger.info("KScore Alert [bi] 생성: %s (risk=%s)", post.id, risk)
    return post


# 하위호환 alias
async def generate_spike_alert(spike, cluster, db):
    """Deprecated: use generate_kscore_alert instead."""
    return await generate_kscore_alert(cluster, db)


# ── Weekly Recap ─────────────────────────────────────────────────────────────

async def generate_weekly_recap(db: AsyncSession) -> SocialPost | None:
    """지난 7일 클러스터 통계 기반 주간 요약 포스트 생성 (bilingual)."""
    now = datetime.now(timezone.utc)
    iso_cal = now.isocalendar()
    dedup_key = f"weekly_recap:{iso_cal.year}-W{iso_cal.week:02d}"

    existing = await db.execute(
        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none():
        logger.info("Weekly Recap 이미 존재: %s", dedup_key)
        return None

    cutoff = now - timedelta(days=7)

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

    total_result = await db.execute(
        select(func.count())
        .select_from(IssueCluster)
        .where(IssueCluster.severity > 0, IssueCluster.last_event_at >= cutoff)
    )
    total_clusters = total_result.scalar() or 0

    country_codes = [s.country_code for s in country_stats[:5] if s.country_code]
    hashtags = _build_hashtags(country_codes)

    stats_lines = []
    for s in country_stats[:5]:
        stats_lines.append(f"- {s.country_code}: {s.event_count} events, avg severity {s.avg_severity:.0f}")

    user_prompt = (
        f"Weekly global conflict stats:\n"
        f"Total {total_clusters} issue clusters\n"
        f"Top countries:\n" + "\n".join(stats_lines)
    )

    body = _call_openai(_WEEKLY_BILINGUAL_SYSTEM, user_prompt)
    if not body:
        top3 = " · ".join(country_codes[:3])
        body = (
            f"📊 Week: {total_clusters} issues | {top3}\n\n"
            f"📊 주간: {total_clusters}개 이슈 | {top3}"
        )

    body = _clean_markdown(body)
    top_severity = int(country_stats[0].avg_severity) if country_stats else 0
    body = body + f"\n\n⚠️ Severity {top_severity}/100"
    if len(body) > 500:
        body = body[:497] + "..."

    post = SocialPost(
        content_type="weekly_recap",
        lang="bi",
        body_text=body,
        hashtags=hashtags,
        risk_level="low",
        dedup_key=dedup_key,
        status="approved",
    )
    db.add(post)
    await db.flush()

    # 카드 배경/이슈용 top 3 클러스터 가져오기
    top_clusters_result = await db.execute(
        select(IssueCluster)
        .where(
            IssueCluster.severity > 0,
            IssueCluster.last_event_at >= cutoff,
        )
        .order_by(IssueCluster.severity.desc())
        .limit(3)
    )
    top_clusters = top_clusters_result.scalars().all()
    await _generate_card_for_post(post, top_clusters or None)
    logger.info("Weekly Recap [bi] 생성: %s", post.id)
    return post
