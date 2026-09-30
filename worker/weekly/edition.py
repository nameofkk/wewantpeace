"""주간 브리핑 한 호 만들기 — 기사 고르기 · AI 브리프(영·한) · 숫자 · 저장.

2026-09-30 진단에서 나온 문제를 막는 설계:
- 예전 뉴스레터는 AI 제공자가 Claude CLI/Groq/OpenAI 뿐이라 7월부터 매주 대체 문구로 나갔다.
  → 스레드와 같은 Gemini 전용 모델(worker/social/brief.py)을 쓰고, AI 브리프가 3건이 안 되면
    status="needs_review" 로 저장해 자동 발송하지 않는다.
- "192개국 위기", 10개국 전부 100점 같은 포화된 지수를 머리 숫자로 썼다.
  → 숫자는 실제로 센 것만: 독립 출처 수, 이번 주 이슈·매체 수, 가격 표에서 직접 계산한 유가 주간 변화.
- 매주 같은 가짜 일정("UN 안보리 긴급 회의")이 박혀 있었다. → 일정 칸은 없앤다.
- 제목 틀("이란, 무장충돌 격화")·출처 1곳짜리가 섞였다. → 스레드와 같은 품질 게이트.

data 모양 (weekly_editions.data):
  week_key, start, end, status_reason
  stories[]  : 본문 기사 5건. cluster_id, cc, lat, lon, n_sources, source_names, first, last,
               photo{url,credit}|None, number{value,en,ko}|None, en{headline,short,what,why,watch}, ko{...}
  also[]     : 이번 주 다른 기사 (제목만). cluster_id, cc, n_sources, en{headline}, ko{headline}
  easing[]   : 협상·휴전 소식 (topic=diplomacy). also 와 같은 모양
  countries  : {cc: {n: 이번 주 기사 수, top: {cluster_id, n_sources, en, ko}}} — "내가 고른 나라" 칸
  advisories : {cc: level} 미 국무부 여행경보 스냅숏 (다음 주 비교용 — 표 자체에 이력이 없다)
  numbers    : {stories, outlets, brent{now, then, pct, now_date, then_date}|None}
  intro      : {en{subject, preheader, intro, lines[3]}, ko{...}}
  images     : {hero_en, hero_ko, map} (render.py 가 채움)
  ai         : {calls, story_ok, intro_ok}
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

LEAD_STORIES = 5
ALSO_STORIES = 5
EASING_STORIES = 3
MIN_SOURCES = 3
MAX_STORY_CALLS = 8          # 전용 모델 무료 할당량(3.5-flash 하루 20건 안팎)을 스레드와 나눠 쓴다
MIN_AI_STORIES = 3           # 이보다 적으면 자동 발송하지 않는다
_CACHE_TTL = 7 * 24 * 3600


# 무기 계약·실적 같은 사업 기사 — 매체가 많이 받아써서 출처 수로는 1번이 된다 (9/30 드라이런에서
# AI 에 건너뛰라고 해도 펜타곤 미사일 계약을 그대로 썼다). AI 앞에서 제목으로 거른다.
BUSINESS_RE = re.compile(r"\b(contracts?|awards?|awarded|procurement|earnings|revenue|shares|stocks?|IPO|stake)\b", re.I)


def week_key(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ── 기사 고르기 ──────────────────────────────────────────────────────────────

async def _candidates(db: AsyncSession, since: datetime, limit: int = 120) -> list:
    from backend.app.models.issue_cluster import IssueCluster
    return (await db.execute(
        select(IssueCluster)
        .where(IssueCluster.last_event_at >= since, IssueCluster.severity > 0)
        .order_by(IssueCluster.kscore.desc())
        .limit(limit)
    )).scalars().all()


def rank_score(cluster, ctx: dict) -> float:
    """얼마나 널리(독립 출처 수) × 얼마나 무거운지(KScore).

    출처 수만 보면 무기 계약·정상회담처럼 매체가 많이 받아쓰는 기사가 1번이 된다
    (9/30 드라이런: 펜타곤 미사일 계약 23곳이 1번). 출처는 20곳에서 자르고 KScore 로 곱한다.
    """
    return min(ctx["n_sources"], 20) * (1.0 + max(cluster.kscore or 0.0, 0.0) / 5.0)


def rank_key(item: tuple) -> tuple:
    cluster, ctx = item
    return (-rank_score(cluster, ctx), -ctx["n_sources"])


def pick_distinct(items: list[tuple], n: int, taken: set, one_per_country: bool = True) -> list[tuple]:
    """앞에서부터 n건 — 이미 뽑은 이슈는 빼고, 나라가 겹치지 않게."""
    out, seen_cc = [], set()
    for cluster, ctx in items:
        if str(cluster.id) in taken:
            continue
        cc = cluster.country_code or ""
        if one_per_country and cc and cc in seen_cc:
            continue
        out.append((cluster, ctx))
        seen_cc.add(cc)
        taken.add(str(cluster.id))
        if len(out) >= n:
            break
    return out


async def select_stories(db: AsyncSession, now: datetime) -> dict:
    """이번 주 후보를 품질 게이트로 거르고 순위를 매긴다 (AI 호출 없음)."""
    from worker.social import brief as B

    since = now - timedelta(days=7)
    qualified = []
    for c in await _candidates(db, since):
        if B.is_template_title(c) or BUSINESS_RE.search(c.title or ""):
            continue
        ctx = await B.gather_context(db, c, hours=24 * 7)
        if ctx["n_sources"] < MIN_SOURCES:
            continue
        qualified.append((c, ctx))
    qualified.sort(key=rank_key)
    return {"qualified": qualified}


# ── AI 브리프 (영·한 한 번에) ────────────────────────────────────────────────

STORY_SYSTEM = (
    "You write one story for a weekly conflict newsletter read by an international audience in "
    "English and by Korean readers in Korean. Return a JSON object with keys: skip, en, ko, number.\n"
    "en and ko are objects with keys: headline, short, what, why, watch.\n"
    "- headline: at most 80 characters (Korean: at most 40 characters), factual, names the place and "
    "the main actor. No trailing period.\n"
    "- short: 3 to 6 words (Korean: at most 16 characters), a label for a numbered list, e.g. "
    "'Settlers raid West Bank villages'.\n"
    "- what: 2 sentences, at most 260 characters (Korean: at most 130 characters). What happened this "
    "week, with numbers and places only if they appear in the reports, and who says so when a claim is "
    "not independently confirmed.\n"
    "- why: 1 sentence, at most 170 characters (Korean: at most 85). Why it matters, grounded in the reports.\n"
    "- watch: 1 sentence, at most 140 characters (Korean: at most 70). The next concrete thing to watch.\n"
    "Korean style: natural Korean news explainer, not a literal translation. Korean headline and short "
    "are headline style (명사형·개조식, e.g. '요르단강 서안 정착민, 팔레스타인 마을 습격') and never end with a "
    "sentence ending. Every Korean sentence in what/why/watch ends in polite 해요체 (-어요/-아요/-했어요/-예요/"
    "-이에요/-거예요); never use -습니다/-ㅂ니다/-다. Use Korean place names (가자지구, 요르단강 서안, 호르무즈 해협).\n"
    "actors: list of the main countries, groups and officials named in the reports. The English and "
    "Korean text must refer to exactly these actors (do not swap countries, e.g. UK is 영국, never 일본).\n"
    "number: the single most telling number reported this week, or null. Object with value (digits "
    "and at most one of + , . % only, e.g. '8', '100+', '720'), en (label under the number, at most 40 "
    "characters, e.g. 'US Marines wounded'), ko (at most 16 characters, e.g. '부상당한 미 해병'). Only "
    "use a number that appears in the reports. Never compute or estimate one. Add source: the outlet "
    "name exactly as written in the square brackets of the report that states the number.\n"
    "skip: true if the reports are not about armed conflict, security, political violence, sanctions "
    "or diplomacy with real-world consequences, or too thin to say what happened. Also true for "
    "business news such as defense contracts, arms procurement deals, company earnings or stock moves.\n"
    "Rules: plain text, no emoji, no hashtags, no exclamation marks, no markdown, no 'BREAKING', no "
    "rhetorical questions. Use only facts present in the reports; never invent casualty figures, names "
    "or quotes. If reports disagree, say that reports differ."
)

INTRO_SYSTEM = (
    "You edit a weekly conflict newsletter. Given this week's stories, return a JSON object with keys "
    "en, ko, titles_ko.\n"
    "en and ko are objects with keys: subject, preheader, intro, lines.\n"
    "- subject: the email subject line. Name the two or three biggest stories concretely, at most 70 "
    "characters (Korean: at most 32 characters). No clickbait, no questions, no 'BREAKING', no emoji. "
    "Example: 'West Bank raids, a missile in Hormuz and Ethiopia's new front'.\n"
    "- preheader: one line shown after the subject in the inbox, at most 90 characters (Korean: 45), "
    "saying what the reader gets, e.g. 'Five stories, each confirmed by at least three outlets.'\n"
    "- intro: two short sentences in a calm, human editor's voice that say what defined the week. "
    "Korean: every sentence ends in polite 해요체 (-어요/-했어요/-예요); never -습니다/-다.\n"
    "- lines: exactly three strings, one line each (at most 70 characters; Korean at most 36), the week "
    "in three lines, each a complete thought.\n"
    "titles_ko: object mapping each given id to a natural Korean headline (at most 40 characters, headline "
    "style, no sentence ending) for the listed other titles.\n"
    "easing_ids: list of ids from easing_candidates that are really about talks, ceasefires, truces, "
    "prisoner or hostage exchanges, humanitarian access or other de-escalation. Leave out arrests, "
    "threats, strikes, sanctions and accusations even if they mention diplomats.\n"
    "Use only facts in the input. Plain text. No emoji."
)


def _cache_get(key: str) -> dict | None:
    try:
        from worker.ai_config import _get_redis_sync
        raw = _get_redis_sync().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: dict) -> None:
    try:
        from worker.ai_config import _get_redis_sync
        _get_redis_sync().set(key, json.dumps(value, ensure_ascii=False), ex=_CACHE_TTL)
    except Exception:
        pass


_KO_RE = re.compile(r"[가-힣]")

# 모델이 해요체 지시를 어기고 합니다체로 쓰는 경우가 잦다 (9/30 드라이런: 본문·서문 절반).
# 규칙이 확실한 어미만 바꾸고, 나머지는 그대로 둔다 (틀리게 바꾸는 것보다 낫다).
_KO_ENDINGS = [
    (re.compile(r"(았|었|였|했|됐|겠|있|없|같)습니다"), r"\1어요"),
    (re.compile(r"합니다"), "해요"),
    (re.compile(r"됩니다"), "돼요"),
    (re.compile(r"보입니다"), "보여요"),
    (re.compile(r"했다\.(\s|$)"), r"했어요.\1"),
]


def _has_batchim(ch: str) -> bool:
    code = ord(ch) - 0xAC00
    return 0 <= code <= 11171 and code % 28 != 0


def normalize_ko(text: str) -> str:
    for pat, sub in _KO_ENDINGS:
        text = pat.sub(sub, text)
    # "…입니다" → 받침 있으면 "이에요", 없으면 "예요"
    def _ipnida(m):
        prev = m.group(1)
        return prev + ("이에요" if _has_batchim(prev) else "예요")
    return re.sub(r"([가-힣])입니다", _ipnida, text)


def _strip_ko_headline(text: str) -> str:
    """제목은 개조식 — 문장 어미로 끝나면 떼어 낸다 ('공격했습니다' → '공격')."""
    return re.sub(r"(했|하였|됐|되었)(습니다|어요|다)$", "", text).rstrip()
_BAD_RE = re.compile(r"[Ѐ-ӿ]")  # 키릴 — 모델이 원문 언어로 답할 때


def clean_story_ai(data: dict | None, source_names: list[str] | None = None) -> dict | None:
    """AI 응답을 검사·정리. 필수 칸이 비었거나 언어가 틀리면 None."""
    from worker.social import brief as B

    if not isinstance(data, dict):
        return None
    if data.get("skip") is True or str(data.get("skip")).lower() == "true":
        return {"skip": True}
    out = {}
    limits = {
        "en": {"headline": 90, "short": 48, "what": 280, "why": 190, "watch": 160},
        "ko": {"headline": 48, "short": 22, "what": 150, "why": 100, "watch": 85},
    }
    for lang, lim in limits.items():
        part = data.get(lang) or {}
        if not isinstance(part, dict):
            return None
        clean = {k: B._fit(B._clean(str(part.get(k, "") or "")).rstrip("." if k in ("headline", "short") else ""), n)
                 for k, n in lim.items()}
        if lang == "ko":
            clean = {k: (_strip_ko_headline(v) if k in ("headline", "short") else normalize_ko(v)) for k, v in clean.items()}
        if not clean["headline"] or not clean["what"]:
            return None
        joined = " ".join(clean.values())
        if _BAD_RE.search(joined):
            return None
        if lang == "en" and _KO_RE.search(joined):
            return None
        if lang == "ko" and not _KO_RE.search(clean["headline"]):
            return None
        out[lang] = clean
    num = data.get("number")
    if isinstance(num, dict) and re.fullmatch(r"[\d][\d.,]*[+%]?", str(num.get("value", "")).strip()):
        out["number"] = {
            "value": str(num["value"]).strip(),
            "en": B._fit(B._clean(str(num.get("en", ""))), 44),
            "ko": B._fit(B._clean(str(num.get("ko", ""))), 20),
            "source": B._clean(str(num.get("source", "")))[:60],
        }
        # 어느 매체가 말한 숫자인지 밝힐 수 없으면 싣지 않는다 (큰 숫자는 라벨이 틀리면 오보가 된다)
        allowed = {n.lower() for n in (source_names or [])}
        if not out["number"]["en"] or not out["number"]["ko"] or \
                (allowed and out["number"]["source"].lower() not in allowed):
            out.pop("number")
    return out


def _story_prompt(cluster, ctx: dict) -> str:
    from worker.social import brief as B
    return (
        f"Country: {B.country_name(cluster.country_code) or 'unknown'}\n"
        f"Topic: {cluster.topic}\n"
        f"Cluster title: {cluster.title}\n"
        f"Independent sources this week: {ctx['n_sources']}\n"
        "Write about the situation in the cluster title (same actors, same kind of event, same area; a "
        "follow-up counts). Some reports may be about unrelated topics in the same country; ignore those.\n"
        "Reports from the past 7 days (newest first):\n" + "\n".join(ctx["reports"][:10])
    )


def write_story(cluster, ctx: dict) -> tuple[dict | None, bool]:
    """(브리프, AI를 불렀는지). 캐시가 있으면 부르지 않는다."""
    from worker.social import brief as B

    key = f"weekly:story:{cluster.id}:{hashlib.md5((ctx['reports'][0] if ctx['reports'] else '').encode()).hexdigest()[:8]}"
    cached = _cache_get(key)
    if cached:
        return cached, False
    data = B._call_dedicated(STORY_SYSTEM, _story_prompt(cluster, ctx), max_tokens=2500)
    story = clean_story_ai(data, ctx.get("source_names"))
    if story:
        _cache_set(key, story)
    return story, True


def fallback_intro(stories: list[dict]) -> dict:
    """AI 가 서문을 못 쓸 때 — 기사 짧은 제목을 그대로 잇는다 (지어낸 문장 없음)."""
    en_shorts = [s["en"]["short"] or s["en"]["headline"] for s in stories[:3]]
    ko_shorts = [s["ko"]["short"] or s["ko"]["headline"] for s in stories[:3]]
    return {
        "en": {"subject": ", ".join(en_shorts[:2]) + (" and more" if len(stories) > 2 else ""),
               "preheader": f"{len(stories)} stories this week, each reported by at least {MIN_SOURCES} outlets.",
               "intro": "", "lines": en_shorts},
        "ko": {"subject": " · ".join(ko_shorts[:2]) + (" 외" if len(stories) > 2 else ""),
               "preheader": f"이번 주 기사 {len(stories)}건, 모두 매체 {MIN_SOURCES}곳 이상이 보도했어요.",
               "intro": "", "lines": ko_shorts},
    }


def write_intro(stories: list[dict], others: list[dict], easing_candidates: list[dict] | None = None
                ) -> tuple[dict, dict, bool, list[str]]:
    """(intro, titles_ko, 성공 여부, 협상·휴전으로 확인된 id)."""
    easing_candidates = easing_candidates or []
    from worker.social import brief as B

    payload = {
        "stories": [{"headline": s["en"]["headline"], "what": s["en"]["what"],
                     "country": B.country_name(s["cc"])} for s in stories],
        "other_titles": {o["cluster_id"]: o["en"]["headline"] for o in others},
        "easing_candidates": {o["cluster_id"]: o["en"]["headline"] for o in easing_candidates},
    }
    data = B._call_dedicated(INTRO_SYSTEM, json.dumps(payload, ensure_ascii=False), max_tokens=2500)
    fb = fallback_intro(stories)
    if not isinstance(data, dict):
        return fb, {}, False, []
    intro = {}
    for lang, lim in (("en", (80, 100, 360, 80)), ("ko", (40, 55, 200, 42))):
        part = data.get(lang) or {}
        lines = [B._fit(B._clean(str(x)), lim[3]) for x in (part.get("lines") or []) if str(x).strip()][:3]
        if lang == "ko":
            lines = [normalize_ko(x) for x in lines]
        item = {
            "subject": B._fit(B._clean(str(part.get("subject", ""))), lim[0]),
            "preheader": B._fit(B._clean(str(part.get("preheader", ""))), lim[1]),
            "intro": (normalize_ko if lang == "ko" else str)(B._fit(B._clean(str(part.get("intro", ""))), lim[2])),
            "lines": lines,
        }
        bad = (lang == "en" and _KO_RE.search(" ".join([item["subject"], item["intro"]]))) or \
              (lang == "ko" and not _KO_RE.search(item["subject"]))
        if not item["subject"] or len(lines) < 3 or bad:
            item = fb[lang]
        intro[lang] = item
    titles_ko = {}
    for k, v in (data.get("titles_ko") or {}).items():
        v = B._fit(B._clean(str(v)), 48)
        if _KO_RE.search(v):
            titles_ko[str(k)] = v
    allowed = {o["cluster_id"] for o in easing_candidates}
    easing_ids = [str(i) for i in (data.get("easing_ids") or []) if str(i) in allowed]
    return intro, titles_ko, True, easing_ids


# ── 숫자 ─────────────────────────────────────────────────────────────────────

async def week_numbers(db: AsyncSession, now: datetime, n_stories: int) -> dict:
    since = now - timedelta(days=7)
    outlets = (await db.execute(sa_text(
        """
        SELECT count(DISTINCT re.source_channel_id)
        FROM normalized_events ne JOIN raw_events re ON re.id = ne.raw_event_id
        WHERE ne.event_time >= :since AND COALESCE(ne.source_tier, 'D') <> 'D'
        """), {"since": since})).scalar() or 0
    # commodity_price.change_pct 는 값이 틀려 있어(9/30: 95.93→96.28 인데 -6.15%) 가격으로 직접 계산한다
    rows = (await db.execute(sa_text(
        "SELECT price_date, price_usd FROM commodity_price WHERE symbol='BRENT' ORDER BY price_date DESC LIMIT 12"
    ))).all()
    brent = None
    if rows:
        now_date, now_px = rows[0]
        target = (datetime.fromisoformat(now_date) - timedelta(days=7)).date().isoformat()
        then = next(((d, p) for d, p in rows if d <= target), None)
        if then and then[1]:
            brent = {"now": round(now_px, 2), "then": round(then[1], 2), "now_date": now_date,
                     "then_date": then[0], "pct": round((now_px - then[1]) / then[1] * 100, 1)}
    return {"stories": n_stories, "outlets": int(outlets), "brent": brent}


async def advisory_levels(db: AsyncSession) -> dict:
    rows = (await db.execute(sa_text(
        "SELECT country_code, level FROM travel_advisory WHERE source='us_state_dept'"
    ))).all()
    return {cc: int(lv) for cc, lv in rows if cc}


# ── 한 호 조립 ───────────────────────────────────────────────────────────────

def _ko_title(cluster) -> str | None:
    """번역 제목이 자동 폴백(나라+토픽 틀)이면 None."""
    from worker.processor.clusterer import _make_fallback_titles
    if not cluster.title_ko:
        return None
    _, fb = _make_fallback_titles(cluster.topic or "", cluster.country_code)
    return None if cluster.title_ko.strip() == fb else cluster.title_ko.strip()


def _brief_item(cluster, ctx: dict) -> dict:
    from worker.social import brief as B
    en = B._fit(B._clean(cluster.title or ""), 110)
    return {"cluster_id": str(cluster.id), "cc": cluster.country_code, "n_sources": ctx["n_sources"],
            "en": {"headline": en}, "ko": {"headline": _ko_title(cluster) or ""}}


async def build_edition(db: AsyncSession, now: datetime | None = None, *, use_ai: bool = True) -> dict:
    """이번 주 호 데이터를 만든다 (저장은 save_edition). use_ai=False 는 테스트·미리보기용."""
    from worker.social import brief as B

    now = now or datetime.now(timezone.utc)
    sel = await select_stories(db, now)
    qualified = sel["qualified"]
    taken: set = set()

    stories: list[dict] = []
    calls = 0
    pool = pick_distinct(qualified, LEAD_STORIES + 6, set())  # 건너뛸 것 대비 여유분
    for cluster, ctx in pool:
        if len(stories) >= LEAD_STORIES:
            break
        ai = None
        if use_ai and calls < MAX_STORY_CALLS:
            ai, called = write_story(cluster, ctx)
            calls += int(called)
            if ai and ai.get("skip"):
                continue
        taken.add(str(cluster.id))
        photos = [{"url": u, "credit": c} for u, c in (ctx.get("photos") or [])[:4]]
        item = {
            "cluster_id": str(cluster.id), "cc": cluster.country_code,
            "lat": cluster.lat, "lon": cluster.lon,
            "n_sources": ctx["n_sources"], "source_names": ctx["source_names"][:8],
            "kscore": round(cluster.kscore or 0, 2), "topic": cluster.topic,
            "first": cluster.first_event_at.isoformat() if cluster.first_event_at else None,
            "last": cluster.last_event_at.isoformat() if cluster.last_event_at else None,
            # 첫 장이 안 받아지면 render.py 가 다음 장을 쓴다 (매체가 핫링크를 막는 경우)
            "photo": photos[0] if photos else None,
            "photos": photos,
            "ai": bool(ai),
        }
        if ai:
            item.update({"en": ai["en"], "ko": ai["ko"], "number": ai.get("number")})
        else:
            base = _brief_item(cluster, ctx)
            ko_head = base["ko"]["headline"] or base["en"]["headline"]
            item.update({"en": {"headline": base["en"]["headline"], "short": "", "what": "", "why": "", "watch": ""},
                         "ko": {"headline": ko_head, "short": "", "what": "", "why": "", "watch": ""},
                         "number": None})
        stories.append(item)

    # 토픽 라벨(diplomacy)은 체포·위협 기사도 섞여 있어(9/30 드라이런) 후보만 넉넉히 뽑고 AI 가 확인한 것만 싣는다
    easing = [_brief_item(c, x) for c, x in
              pick_distinct([q for q in qualified if (q[0].topic or "") == "diplomacy"], EASING_STORIES * 3, set(taken))]
    also = [_brief_item(c, x) for c, x in pick_distinct(qualified, ALSO_STORIES, taken)]

    countries: dict = {}
    for cluster, ctx in qualified:
        cc = cluster.country_code
        if not cc:
            continue
        entry = countries.setdefault(cc, {"n": 0, "top": None})
        entry["n"] += 1
        if entry["top"] is None:
            entry["top"] = _brief_item(cluster, ctx)

    story_ok = sum(1 for s in stories if s["ai"])
    intro_ok = False
    titles_ko: dict = {}
    if use_ai and stories and story_ok:
        others = easing + also + [c["top"] for c in countries.values() if c["top"]][:30]
        intro, titles_ko, intro_ok, easing_ids = write_intro([s for s in stories if s["ai"]] or stories, others, easing)
        easing = [e for e in easing if e["cluster_id"] in easing_ids][:EASING_STORIES]
    else:
        intro = fallback_intro(stories) if stories else {}
        easing = []  # AI 확인 없이는 싣지 않는다
    easing_ids_final = {e["cluster_id"] for e in easing}
    also = [a for a in also if a["cluster_id"] not in easing_ids_final]
    for item in easing + also + [c["top"] for c in countries.values() if c["top"]]:
        if not item["ko"]["headline"]:
            item["ko"]["headline"] = titles_ko.get(item["cluster_id"]) or item["en"]["headline"]

    status_reason = None
    if story_ok < MIN_AI_STORIES:
        status_reason = f"ai_stories<{MIN_AI_STORIES} ({story_ok})"

    return {
        "week_key": week_key(now),
        "start": (now - timedelta(days=7)).date().isoformat(),
        "end": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "status_reason": status_reason,
        "stories": stories,
        "also": also,
        "easing": easing,
        "countries": countries,
        "advisories": await advisory_levels(db),
        "numbers": await week_numbers(db, now, len(qualified)),
        "intro": intro,
        "images": {},
        "ai": {"calls": calls + (1 if intro_ok or (use_ai and story_ok) else 0), "story_ok": story_ok, "intro_ok": intro_ok},
    }


async def save_edition(db: AsyncSession, data: dict):
    from backend.app.models.weekly_edition import WeeklyEdition

    row = (await db.execute(select(WeeklyEdition).where(WeeklyEdition.week_key == data["week_key"]))).scalar_one_or_none()
    status = "needs_review" if data.get("status_reason") else "ready"
    if row is None:
        row = WeeklyEdition(week_key=data["week_key"], data=data, status=status)
        db.add(row)
    else:
        row.data = data
        row.status = status
    await db.flush()
    return row


async def latest_edition(db: AsyncSession, max_age_days: int = 8):
    from backend.app.models.weekly_edition import WeeklyEdition

    since = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return (await db.execute(
        select(WeeklyEdition).where(WeeklyEdition.created_at >= since)
        .order_by(WeeklyEdition.created_at.desc()).limit(1)
    )).scalar_one_or_none()
