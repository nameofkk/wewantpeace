"""
GDELT 2.0 GKG 15분 파일 수집기.

2026-10-02 교체: 예전엔 DOC API(api.gdeltproject.org/api/v2/doc/doc)를 썼는데, 그 API 는
"5초에 한 번" 제한이 걸려 있고 Railway 공용 IP 에서는 매번 429 로 거절돼 지난 7일 수집이 0건이었다.
GDELT 는 15분마다 전 세계 기사 분석 결과를 파일(GKG: Global Knowledge Graph)로도 공개한다
(data.gdeltproject.org/gdeltv2/lastupdate.txt). 요청 제한이 없고, 기사마다 URL·매체 도메인·제목·
테마·장소·감성 점수·대표 이미지가 들어 있다. 15분 파일 하나에 기사 약 900건, 3.6MB(zip).

거르는 법: 지역 범죄·연예 기사가 대부분이라 분쟁 테마가 확실한 기사만 고른다.
  - 강한 테마(ARMED_CONFLICT·TERROR·MILITARY·REBELLION·COUP …)가 있어야 한다
  - 제목이 있어야 하고 감성 점수가 음수여야 한다
  - 우리 RSS 로 이미 받는 매체 도메인은 뺀다 (같은 기사 두 번 세지 않게)
  - 점수(강한 테마 수 + 부정 감성) 순으로 한 번에 최대 MAX_PER_RUN 건
분류는 GKG 테마·장소로 바로 정한다(raw_metadata.structured_*) → AI 분류 호출을 쓰지 않는다.
"""
import io
import logging
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent
from backend.app.models.source_channel import SourceChannel

logger = logging.getLogger(__name__)

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
MAX_PER_RUN = 25

# 분쟁 기사로 확정해 주는 테마 (GKG V1 Themes 필드)
STRONG_THEMES = (
    "ARMED_CONFLICT", "TERROR", "MILITARY", "REBELLION", "COUP", "SEIGE", "BLOCKADE",
    "WMD", "SUICIDE_ATTACK", "KIDNAP", "REFUGEES", "CEASEFIRE", "PEACEKEEPING", "INSURGENCY",
    "WB_2433_CONFLICT_AND_VIOLENCE", "WB_2432_FRAGILITY_CONFLICT_AND_VIOLENCE",
)
# 테마 → 우리 토픽 (앞에 있는 것이 우선)
THEME_TOPIC = (
    ("COUP", "coup"), ("TERROR", "terror"), ("SUICIDE_ATTACK", "terror"), ("CYBER_ATTACK", "cyber"),
    ("SANCTIONS", "sanctions"), ("PROTEST", "protest"), ("MARITIME", "maritime"), ("PIRACY", "maritime"),
    ("CEASEFIRE", "diplomacy"), ("PEACE", "diplomacy"), ("NEGOTIATIONS", "diplomacy"),
    ("ARMED_CONFLICT", "conflict"), ("MILITARY", "conflict"), ("REBELLION", "conflict"),
    ("SEIGE", "conflict"), ("KILL", "conflict"), ("INSURGENCY", "conflict"),
)
# 지역 범죄 기사 표시 (분쟁 테마가 같이 붙어도 이게 있고 MILITARY/ARMED_CONFLICT 가 없으면 뺀다)
_CRIME_HINT = re.compile(r"\b(police|sheriff|murder|homicide|shooting|stabbing|sentenced|jury|trial|arrested)\b", re.I)


@dataclass
class GDELTCollectResult:
    display_name: str = "GDELT"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _title(extras: str) -> str:
    m = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", extras or "", re.S)
    if not m:
        return ""
    import html as _html
    t = re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip()
    # "기사 제목 | 매체명" 꼬리 떼기 — 마지막 구분자 뒤가 짧을 때만(매체명), 제목 안의 대시는 남긴다
    parts = re.split(r"\s+[|–—-]\s+", t)
    while len(parts) > 1 and len(parts[-1].split()) <= 4:
        parts = parts[:-1]
    return " – ".join(parts)[:300]


def _country(locations: str) -> tuple[str | None, float | None, float | None]:
    """V1 Locations: type#FullName#FIPS#ADM1#lat#lon#featureID ; 가장 많이 나온 나라 이름과 첫 좌표."""
    names, coords = Counter(), {}
    for loc in (locations or "").split(";"):
        p = loc.split("#")
        if len(p) < 7:
            continue
        full = p[1]
        name = full.split(",")[-1].strip() if full else ""
        if not name:
            continue
        names[name] += 1
        if name not in coords:
            try:
                coords[name] = (float(p[4]), float(p[5]))
            except ValueError:
                pass
    if not names:
        return None, None, None
    name = names.most_common(1)[0][0]
    lat, lon = coords.get(name, (None, None))
    return name, lat, lon


def score_row(themes: str, tone: float, title: str) -> int | None:
    """분쟁 기사면 점수, 아니면 None."""
    strong = [t for t in STRONG_THEMES if t in themes]
    if not strong or not title or tone >= 0:
        return None
    hard = any(t in themes for t in ("ARMED_CONFLICT", "MILITARY", "REBELLION", "TERROR", "COUP"))
    if not hard and _CRIME_HINT.search(title):
        return None
    return len(strong) * 3 + int(min(10, -tone))


def topic_of(themes: str) -> str:
    for key, topic in THEME_TOPIC:
        if key in themes:
            return topic
    return "conflict"


_KEEP_TOPICS = {"conflict", "terror", "coup", "protest", "sanctions", "cyber", "maritime", "diplomacy"}
MIN_SCORE = 10
_CONFLICT_WORD = re.compile(
    r"\b(terror\w*|attack\w*|strikes?|airstrikes?|missiles?|rockets?|drones?|troops|soldiers|military|militants?|"
    r"rebels?|insurgents?|army|navy|warships?|bomb\w*|shelling|clash\w*|killed|war|ceasefire|truce|hostages?|"
    r"coup|junta|sanctions?|blockade|houthis?|hamas|hezbollah|taliban|isis|al-shabaab|jihadist\w*|militia\w*)\b",
    re.I,
)
# 테마·키워드가 분쟁이어도 실제로는 아닌 제목 (10-02 실측 오탐: OTT 드라마 소개, 교통사고, 의료보험, 소송, 칼럼)
_NOT_CONFLICT = re.compile(
    r"\b(web series|series|film|movie|OTT|netflix|box office|crash|collision|medicaid|insurance|lawsuit|sues|"
    r"jail time|faces jail|sentenced|trial|court|editors?|op-?ed|opinion|column|review|recipe|stocks?|shares|"
    r"earnings|IPO|weather|football|cricket|soccer|nfl|nba|home invasions?|predator|sting|arrest report|"
    r"cyberstalking|roundup|obituary)\b",
    re.I,
)


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower())[:80]


def parse_gkg(text: str, skip_domains: set[str]) -> list[dict]:
    """GKG 파일 → 분쟁 기사 후보 (점수순).

    GKG 테마는 넓게 붙는다(10-02 실측: 미국 소송 기사에 TERROR, 인도 OTT 드라마 소개에 MILITARY).
    그래서 테마 + 제목 키워드 분류(normalizer._classify_topic) 둘 다 분쟁 쪽이어야 남기고,
    토픽도 제목 키워드 분류를 따른다. 지역지 수십 곳이 같은 통신 기사를 그대로 싣는 경우가 많아
    (Newsquest·NPR 계열) 같은 제목은 한 건만 남긴다 — 같은 기사를 여러 매체로 세지 않는다.
    """
    from worker.processor.normalizer import _classify_topic, _is_entertainment_noise
    rows = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 27:
            continue
        url, domain_name = f[4], (f[3] or "").lower()
        domain = _domain(url) or domain_name
        if not url.startswith("http") or domain in skip_domains or domain_name in skip_domains:
            continue
        themes = f[7] or ""
        try:
            tone = float((f[15] or "0").split(",")[0])
        except ValueError:
            tone = 0.0
        title = _title(f[26])
        sc = score_row(themes, tone, title)
        if sc is None:
            continue
        if sc < MIN_SCORE or _NOT_CONFLICT.search(title):
            continue
        if _is_entertainment_noise(title, title=title):
            continue
        kw_topic = _classify_topic(title)
        if kw_topic not in _KEEP_TOPICS:
            # 제목 키워드 사전이 못 잡는 표현('terror plot' 등)은 제목에 분쟁 단어가 있을 때만 테마로 정한다.
            # 테마 개수만 보면 SF 영화 목록·스토킹 기소 같은 기사가 들어왔다 (10-02 실측)
            if not _CONFLICT_WORD.search(title):
                continue
            kw_topic = topic_of(themes)
        country, lat, lon = _country(f[9])
        if not country:
            continue  # 어디서 일어난 일인지 모르면 지도·나라 묶음에 못 붙인다
        rows.append({
            "score": sc, "url": url, "domain": domain, "title": title, "tone": tone, "themes": themes,
            "topic": kw_topic, "country": country, "lat": lat, "lon": lon,
            "image": f[18] if (f[18] or "").startswith("http") else "", "date": f[1],
        })
    rows.sort(key=lambda r: -r["score"])
    # 같은 매체에서 여러 건이면 상위 2건만 (한 매체가 수집분을 독차지하지 않게)
    out, per_domain, seen_titles = [], Counter(), set()
    for r in rows:
        key = _norm_title(r["title"])
        if per_domain[r["domain"]] >= 2 or key in seen_titles:
            continue
        per_domain[r["domain"]] += 1
        seen_titles.add(key)
        out.append(r)
    return out


def severity_of(topic: str, tone: float, n_strong: int) -> int:
    from worker.processor.normalizer import TOPIC_BASE_SEVERITY
    base = TOPIC_BASE_SEVERITY.get(topic, 40)
    return max(10, min(90, base + int(min(15, -tone * 1.5)) + min(10, n_strong * 2)))


class GDELTCollector:
    """GDELT GKG 15분 파일 수집기."""

    TIMEOUT = 60

    async def _rss_domains(self, db: AsyncSession) -> set[str]:
        urls = (await db.execute(select(SourceChannel.feed_url).where(
            SourceChannel.is_active == True, SourceChannel.feed_url.isnot(None)))).scalars().all()  # noqa: E712
        doms = set()
        for u in urls:
            d = _domain(u or "")
            if d.startswith("news.google.com"):
                m = re.search(r"site:([a-z0-9.\-]+)", u or "")
                d = m.group(1) if m else ""
            for prefix in ("feeds.", "rss.", "www3.", "en."):
                if d.startswith(prefix):
                    d = d[len(prefix):]
            if d:
                doms.add(d)
        return doms

    async def collect(self, source: SourceChannel, db: AsyncSession, redis=None) -> GDELTCollectResult:
        result = GDELTCollectResult(display_name=source.display_name)
        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": "WeWantPeace/1.0 (+https://www.wewantpeace.live)"}) as client:
            lu = (await client.get(LASTUPDATE_URL)).text.strip().splitlines()
            gkg_url = next((l.split()[-1] for l in lu if l.endswith(".gkg.csv.zip")), None)
            if not gkg_url:
                result.errors.append("lastupdate 에 GKG 파일 없음")
                return result
            latest = gkg_url.rsplit("/", 1)[-1].split(".")[0]
            # lastupdate 에 올라온 직후엔 파일이 아직 없을 때가 있다(10-02 배포 직후 404) → 15분 전 파일로
            from datetime import timedelta
            prev = (datetime.strptime(latest, "%Y%m%d%H%M%S") - timedelta(minutes=15)).strftime("%Y%m%d%H%M%S")
            resp, stamp = None, None
            for cand in (latest, prev):
                if source.last_fetch_cursor and cand <= source.last_fetch_cursor:
                    break  # 이미 처리한 파일
                r = await client.get(f"http://data.gdeltproject.org/gdeltv2/{cand}.gkg.csv.zip")
                if r.status_code == 200:
                    resp, stamp = r, cand
                    break
            if resp is None:
                return result
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            text = zf.read(zf.namelist()[0]).decode("utf-8", "replace")

        rows = parse_gkg(text, await self._rss_domains(db))
        for r in rows:
            if result.collected >= MAX_PER_RUN:
                break
            ext_id = "gdelt:" + __import__("hashlib").md5(r["url"].encode()).hexdigest()
            # 지역지 수십 곳이 같은 통신 기사를 15분·30분 간격으로 실어 올린다 — 같은 제목은 48시간 동안 한 번만
            tkey = "gdelt:title:" + __import__("hashlib").md5(_norm_title(r["title"]).encode()).hexdigest()
            if redis is not None:
                try:
                    if not await redis.set(tkey, "1", ex=48 * 3600, nx=True):
                        result.skipped += 1
                        continue
                except Exception:
                    pass
            exists = (await db.execute(select(RawEvent.id).where(
                RawEvent.source_type == "api", RawEvent.external_id == ext_id))).scalar_one_or_none()
            if exists:
                result.skipped += 1
                continue
            try:
                published = datetime.strptime(r["date"], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                published = datetime.now(timezone.utc)
            n_strong = sum(1 for t in STRONG_THEMES if t in r["themes"])
            meta = {
                "title": r["title"],
                "link": r["url"],
                "domain": r["domain"],
                "source_name": r["domain"],   # 독립 출처 수를 셀 때 매체 단위로 센다 (worker/social/brief.py)
                "aggregator": "gdelt",
                "tone": r["tone"],
                "themes": [t for t in r["themes"].split(";") if t][:15],
                "published": published.isoformat(),
                "time_source": "gdelt_gkg",
                "structured_topic": r["topic"],
                "structured_severity": severity_of(r["topic"], r["tone"], n_strong),
                "image_url": r["image"],
            }
            # 나라: 제목에서 잡히면 그걸 쓴다(처리 단계가 제목으로 다시 뽑는다). GKG '가장 많이 나온 장소'는
            # 본문에 언급된 나라라 엇나가기 쉽다 (10-02 드라이런: 이집트 군사원조 기사 → 이스라엘)
            from worker.processor.normalizer import _extract_geo
            title_cc, _, _ = _extract_geo(r["title"], title=r["title"])
            if not title_cc and r["country"] and r["lat"] is not None:
                meta.update({"structured_country": r["country"], "structured_lat": r["lat"], "structured_lon": r["lon"]})
            ev = RawEvent(source_channel_id=source.id, source_type="api", external_id=ext_id,
                          raw_text=r["title"], raw_metadata=meta, lang="en",
                          collected_at=datetime.now(timezone.utc))
            db.add(ev)
            result.raw_event_ids.append(ev)
            result.collected += 1
        result.skipped += max(0, len(rows) - result.collected - result.skipped)
        source.last_fetch_cursor = stamp
        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[GDELTCollectResult]:
        channels = (await db.execute(select(SourceChannel).where(
            SourceChannel.is_active == True,  # noqa: E712
            SourceChannel.source_type == "api",
            SourceChannel.display_name.ilike("%gdelt%"),
        ))).scalars().all()
        results = []
        for ch in channels:
            try:
                res = await self.collect(ch, db, redis=redis)
                logger.info("GDELT 수집 완료: %s (collected=%d, skipped=%d, errors=%s)",
                            ch.display_name, res.collected, res.skipped, res.errors)
                results.append(res)
            except Exception as e:
                logger.exception("GDELT 수집 오류")
                results.append(GDELTCollectResult(errors=[str(e)[:200]]))
        return results
