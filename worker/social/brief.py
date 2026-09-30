"""Threads 영어 브리프 — 출처 수집 · 품질 게이트 · AI 요약 · 본문 조립.

2026-09-30 개편 배경:
- 해외 실사용자가 90%인데 게시물이 한·영 혼합 + 이모지 + "BREAKING" 톤이었다.
- 하루 33건이 무차별로 나갔고, 템플릿 제목("Iran Conflict")·출처 1개짜리도 섞였다.
- Threads 에서 무게가 큰 신호는 답글·프로필 클릭이고, 사진 게시물이 텍스트보다 반응이 높다.
  낚시성 질문·홍보 문구는 불이익 대상이라 정보 자체로 멈춰 세우는 쪽을 택했다.

형식: 무슨 일이 있었나 / 왜 중요한가 / 무엇을 지켜볼까 + "독립 출처 N곳".
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SITE = "https://www.wewantpeace.live"
THREADS_LIMIT = 500

# 이모지·국기·장식 기호 — AI 가 넣더라도 게시 전에 전부 걷어낸다
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "☀-➿"
    "⬀-⯿"
    "‍️⃣"
    "]+",
    re.UNICODE,
)


def strip_emoji(text: str) -> str:
    text = _EMOJI_RE.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _clean(text: str) -> str:
    text = strip_emoji(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"#(\w+)", r"\1", text)  # 본문 해시태그 제거 (주제 태그는 API 파라미터로)
    text = re.sub(r"(?i)^\s*(breaking|urgent|just in)\s*[:\-–]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def country_name(cc: str | None) -> str:
    from worker.processor.clusterer import _COUNTRY_NAMES_EN
    if not cc:
        return ""
    name = _COUNTRY_NAMES_EN.get(cc.upper(), cc.upper())
    return {"US": "United States", "UK": "United Kingdom"}.get(name, name)


def topic_tag_for(cc: str | None, topic: str | None = None) -> str:
    """Threads 주제 태그 1개 (1~50자, 마침표·& 불가). 나라 이름이 가장 검색되는 단위."""
    name = country_name(cc)
    if name:
        return name.replace(".", "").replace("&", "and")[:50]
    return {"cyber": "Cybersecurity", "diplomacy": "Geopolitics"}.get(topic or "", "Geopolitics")


def issue_url(cluster_id) -> str:
    return f"{SITE}/issues/{cluster_id}?ref=threads"


# ── 출처 수집 ────────────────────────────────────────────────────────────────

async def gather_context(db: AsyncSession, cluster, hours: int = 48) -> dict:
    """클러스터의 최근 이벤트·출처를 모은다.

    독립 출처 수는 D등급(미검증·선전 채널)을 뺀 서로 다른 source_channel 수.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (await db.execute(
        sa_text(
            """
            SELECT ne.title, ne.body, ne.event_time, ne.source_tier, ne.image_url,
                   sc.id AS channel_id, sc.display_name
            FROM cluster_events ce
            JOIN normalized_events ne ON ne.id = ce.event_id
            LEFT JOIN raw_events re ON re.id = ne.raw_event_id
            LEFT JOIN source_channels sc ON sc.id = re.source_channel_id
            WHERE ce.cluster_id = :cid AND ne.event_time >= :since
            ORDER BY ne.event_time DESC
            LIMIT 60
            """
        ),
        {"cid": cluster.id, "since": since},
    )).mappings().all()

    tier_rank = {"A": 0, "B": 1, "C": 2}
    channels: dict = {}
    for r in rows:
        if r["channel_id"] is None or (r["source_tier"] or "D") == "D":
            continue
        rank = tier_rank.get(r["source_tier"], 3)
        prev = channels.get(r["channel_id"])
        if prev is None or rank < prev[0]:
            channels[r["channel_id"]] = (rank, r["display_name"])
    source_names = [name for _, name in sorted(channels.values())]

    reports = []
    for r in rows[:10]:
        if (r["source_tier"] or "D") == "D":
            continue
        body = re.sub(r"\s+", " ", r["body"] or "")[:280]
        reports.append(f"- [{r['display_name'] or 'unknown'}] {r['title']} — {body}")

    # 카드뉴스 장마다 다른 기사 사진 — 믿을 만한 출처(A/B) 사진부터, 같은 사진은 한 번만
    photos: list[tuple[str, str]] = []
    seen: set[str] = set()
    for r in sorted(rows, key=lambda r: tier_rank.get(r["source_tier"], 3)):
        url = r["image_url"]
        if not url or not url.startswith("http") or url in seen or (r["source_tier"] or "D") == "D":
            continue
        seen.add(url)
        photos.append((url, r["display_name"] or ""))
    cover = getattr(cluster, "image_url", None)
    if cover and cover.startswith("http") and cover not in seen:
        photos.insert(0, (cover, ""))

    newest = rows[0]["event_time"] if rows else None
    return {
        "n_sources": len(source_names),
        "source_names": source_names,
        "reports": reports,
        "photos": photos[:6],
        "newest_event_at": newest,
    }


# ── 품질 게이트 ──────────────────────────────────────────────────────────────

def is_template_title(cluster) -> bool:
    from worker.processor.clusterer import _is_junk_title, _make_fallback_titles
    title = (cluster.title or "").strip()
    if not title or _is_junk_title(title):
        return True
    fallback_en, _ = _make_fallback_titles(cluster.topic or "", cluster.country_code)
    return title.lower() == fallback_en.lower()


def quality_reject_reason(cluster, ctx: dict, min_sources: int) -> str | None:
    if is_template_title(cluster):
        return "template_title"
    if ctx["n_sources"] < min_sources:
        return f"sources<{min_sources}"
    newest = ctx.get("newest_event_at")
    if not newest or datetime.now(timezone.utc) - newest > timedelta(hours=48):
        return "stale"
    return None


# ── AI 브리프 ────────────────────────────────────────────────────────────────

BRIEF_SYSTEM = (
    "You are an analyst writing a short, neutral conflict brief for an international "
    "English-speaking audience on Threads. Return a JSON object with exactly these keys: "
    "skip, headline, highlight, dek, what, why, watch.\n"
    "highlight: the 2 to 4 most important consecutive words copied exactly from headline "
    "(they are shown in a different colour on the cover card).\n"
    "dek: one short line under the headline on the cover, at most 90 characters, adding the key "
    "fact the headline leaves out (a number, a place, who said it). No trailing period.\n"
    "skip: true if the reports are not about armed conflict, security, political violence, "
    "sanctions or diplomacy with real-world consequences (for example forum discussions, sports, "
    "entertainment, opinion pieces, product news or anniversaries), or if they are too thin to "
    "state what happened. When skip is true the other keys may be empty.\n"
    "Rules:\n"
    "- English only. Plain text. No emoji, no hashtags, no exclamation marks, no markdown.\n"
    "- No 'BREAKING', no clickbait, no rhetorical questions, no calls to follow or like.\n"
    "- headline: at most 80 characters, factual, names the place and the main actor, "
    "sentence case, no trailing period.\n"
    "- what: 1-2 sentences, at most 170 characters. What happened, with numbers and places "
    "only if they appear in the reports.\n"
    "- why: 1 sentence, at most 130 characters. Why it matters (escalation risk, civilians, "
    "trade routes, diplomacy), grounded in the reports.\n"
    "- watch: 1 sentence, at most 110 characters. The next concrete thing to watch "
    "(a response, a meeting, a deadline) or the signal that would show escalation or de-escalation.\n"
    "- Use only facts present in the reports. Never invent casualty figures, names or quotes. "
    "If reports disagree, say that reports differ."
)


def _parse_json(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def _call_dedicated(system: str, user: str) -> dict | None:
    """브리프 전용 Gemini 모델 — 분류 파이프라인과 무료 할당량을 나눠 쓰지 않는다.

    Gemini 무료 할당량은 모델별로 따로다. 9/30 실측: 분류가 쓰는 3.5-flash-lite(하루 500건)와
    Groq(하루 20만 토큰)가 둘 다 바닥난 시각에도 3.5-flash 는 응답했다. 브리프는 하루 몇 건뿐이라
    전용 모델 하나로 충분하고, 글 품질도 lite 보다 낫다.
    """
    import os
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    # 3.5-flash 는 가끔 503(수요 과다)을 낸다 — 할당량이 모델마다 따로라 3-flash-preview, 3.1-flash-lite 를 뒤에 (2.5-flash 는 신규 계정 불가)
    models = [m.strip() for m in os.getenv("SOCIAL_BRIEF_MODELS", "gemini-3.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite").split(",") if m.strip()]
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", timeout=30.0)
    for model in models:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"},
                reasoning_effort="low",
            )
            data = _parse_json((resp.choices[0].message.content or "").strip())
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("브리프 전용 모델(%s) 실패: %s", model, str(exc)[:160])
    return None


_AI_CALLS = 0  # 프로세스 안 누적 호출 수 — 호출부가 한 번 실행에 쓸 수 있는 호출 수를 제한할 때 쓴다
_SKIP_TTL = 12 * 3600


def ai_call_count() -> int:
    return _AI_CALLS


def recently_skipped(cluster_id) -> bool:
    """AI 가 최근 12시간 안에 '게시할 사건 아님'이라 했거나 요약에 실패한 클러스터.

    전용 모델 무료 할당량이 하루 20건 안팎이라(9/30 실측) 30분마다 같은 클러스터를
    다시 묻지 않는다.
    """
    try:
        from worker.ai_config import _get_redis_sync
        return bool(_get_redis_sync().exists(f"social:brief_skip:{cluster_id}"))
    except Exception:
        return False


def remember_skip(cluster_id) -> None:
    try:
        from worker.ai_config import _get_redis_sync
        _get_redis_sync().set(f"social:brief_skip:{cluster_id}", "1", ex=_SKIP_TTL)
    except Exception:
        pass


def _call_ai_json(system: str, user: str) -> dict | None:
    global _AI_CALLS
    _AI_CALLS += 1
    data = _call_dedicated(system, user)
    if isinstance(data, dict):
        return data
    return _call_shared(system, user)


def _call_shared(system: str, user: str) -> dict | None:
    """현재 제공자로 부르고, 429 면 차단을 기록해 다음 제공자(Groq → Gemini)로 한 번 더.

    Groq 일일 토큰(200K)은 분류 파이프라인이 먼저 다 쓰는 날이 있다 (9/30 실측: 199,999 사용).
    차단 기록은 normalizer 와 같은 Redis 키를 써서 다른 작업도 같이 Gemini 로 넘어간다.
    """
    from openai import RateLimitError
    from worker.ai_config import (
        get_client, get_model, get_current_provider, is_available,
        mark_rate_limited, mark_gemini_rate_limited,
    )
    for _ in range(2):
        if not is_available():
            return None
        provider = get_current_provider()
        try:
            client = get_client(timeout=20.0)
            extra = {"reasoning_effort": "minimal"} if provider == "gemini" else {}
            resp = client.chat.completions.create(
                model=get_model(),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.3,
                # 추론 모델은 본문 전에 reasoning 토큰을 쓴다 — 넉넉히
                max_tokens=1200,
                response_format={"type": "json_object"},
                **extra,
            )
            return _parse_json((resp.choices[0].message.content or "").strip())
        except RateLimitError as exc:
            if provider == "groq":
                wait = 300.0
                mm = re.search(r"try again in (\d+)m([\d.]+)s", str(exc))
                if mm:
                    wait = int(mm.group(1)) * 60 + float(mm.group(2)) + 30
                mark_rate_limited(min(wait, 900.0))
            elif provider == "gemini":
                mark_gemini_rate_limited(60.0)
            logger.warning("브리프 AI 429 (%s) — 다음 제공자로 재시도", provider)
        except Exception:
            logger.exception("브리프 AI 호출 실패 (%s)", provider)
            return None
    return None


def _fit(text: str, limit: int) -> str:
    """문장 경계에서 자르고, 안 되면 단어 경계에서 자른다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dot = max(cut.rfind(". "), cut.rfind("; "))
    if dot > limit * 0.5:
        return cut[: dot + 1].strip()
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


def build_brief(cluster, ctx: dict) -> dict | None:
    user = (
        f"Country: {country_name(cluster.country_code) or 'unknown'}\n"
        f"Topic: {cluster.topic}\n"
        f"Cluster title: {cluster.title}\n"
        f"Independent sources: {ctx['n_sources']}\n"
        "Write about the situation in the cluster title: the same actors and the same kind of "
        "event in the same area (a nearby village or a follow-up counts). Some reports below may be "
        "about unrelated topics in the same country; ignore those. Set skip to true only if no "
        "report concerns that situation.\n"
        "Recent reports (newest first):\n" + "\n".join(ctx["reports"][:8])
    )
    data = _call_ai_json(BRIEF_SYSTEM, user)
    if not isinstance(data, dict):
        return None
    if data.get("skip") is True or str(data.get("skip")).lower() == "true":
        logger.info("브리프 AI 판단: 게시할 만한 사건 아님 — %s", (cluster.title or "")[:60])
        return None
    brief = {
        "headline": _fit(_clean(str(data.get("headline", ""))).rstrip("."), 90),
        "dek": _fit(_clean(str(data.get("dek", ""))).rstrip("."), 100),
        "what": _fit(_clean(str(data.get("what", ""))), 190),
        "why": _fit(_clean(str(data.get("why", ""))), 150),
        "watch": _fit(_clean(str(data.get("watch", ""))), 130),
    }
    if not brief["headline"] or not brief["what"]:
        return None
    # 영어 브리프에 한글·키릴 문자가 섞이면 버린다 (모델이 가끔 원문 언어로 답함)
    if re.search(r"[가-힣Ѐ-ӿ]", " ".join(brief.values())):
        return None
    hl = _clean(str(data.get("highlight", "")))
    brief["highlight"] = hl if hl and hl.lower() in brief["headline"].lower() else ""
    return brief


def _sources_line(source_names: list[str], limit: int = 3) -> str:
    shown = source_names[:limit]
    rest = len(source_names) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def compose_alert_text(brief: dict, n_sources: int, cluster_id, source_names: list[str] | None = None) -> str:
    """Threads 본문 — 레퍼런스(Ground News·Politico·Al Jazeera·so informed)와 같은 틀.

    헤드라인은 표지 카드에 있으니 반복하지 않는다. 뉴스 한 문장 + 맥락 한 문장 + 출처.
    링크·지켜볼 점은 바로 아래 자기 답글로 (so informed·Novara 방식).
    """
    parts = [brief["what"]]
    if brief.get("why"):
        parts.append(brief["why"])
    src = f"Sources: {_sources_line(source_names)}." if source_names else f"{n_sources} independent sources."
    text = "\n\n".join(parts + [src])
    if len(text) > THREADS_LIMIT:
        text = "\n\n".join([brief["what"], src])
    return text[:THREADS_LIMIT]


def compose_sources_reply(source_names: list[str], cc: str | None = None,
                          watch: str | None = None, cluster_id=None) -> str | None:
    """본문 바로 아래 자기 답글 — 지켜볼 점, 전체 타임라인 링크, 주간 브리프 구독.

    so informed·Novara 는 본문은 짧게 두고 자세한 내용과 링크를 자기 답글로 이어 단다.
    """
    parts = []
    if watch:
        parts.append(f"What to watch: {watch}")
    if cluster_id:
        parts.append(f"Full timeline and all sources: {issue_url(cluster_id)}")
    elif source_names:
        parts.append(f"Sources: {_sources_line(source_names, 5)}.")
    name = country_name(cc)
    if name:
        # 주간 브리프 이메일 구독 검증 실험 (2주) — 게시물 본문이 아니라 답글에만
        parts.append(f"A weekly brief on {name} by email: {SITE}/brief?c={cc.upper()}&ref=threads")
    return "\n\n".join(parts)[:THREADS_LIMIT] if parts else None
