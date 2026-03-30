"""
RSS/Atom 피드 수집기.
feedparser 기반으로 source_channels.feed_url에서 항목 수집.

개선사항:
- feedparser.parse()를 asyncio.to_thread()로 블로킹 해소
- asyncio.Semaphore로 동시 HTTP 요청 수 제한 (최대 5개)
- 스팸/노이즈 패턴 필터링 강화
"""
import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import feedparser
from sqlalchemy import select

# 일부 사이트가 feedparser 기본 UA를 차단하므로 브라우저 UA 사용
feedparser.USER_AGENT = (
    "Mozilla/5.0 (compatible; WeWantPeace/1.0; +https://www.wewantpeace.live)"
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.source_channel import SourceChannel
from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# ── 스팸/노이즈 필터 ─────────────────────────────────────────────────────────

# 최소 텍스트 길이 (단어 수 기준)
MIN_WORDS = 8

# 최소 텍스트 길이 (글자 수)
MIN_CHARS = 60

# 스팸 패턴 (정규식, re.IGNORECASE 적용)
_SPAM_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # 블로그/사이트 폐쇄·이전
    r"blog (has been|is (now|currently)) (closed|archived|moved|discontinued)",
    r"this (site|blog|page|website) (has|is|will be|has been)",
    r"we (have|'ve) (moved|closed|shut down|discontinued)",
    r"(site|blog|page) (moved|closed|unavailable|no longer)",
    # 구독 유도 (뉴스레터·앱·팟캐스트)
    r"(sign up|subscribe) (for|to) (our|the|free|breaking|daily)",
    r"(free|breaking|daily) (news|email|newsletter|app|podcast|alert)",
    r"(get|receive|download) (our|the) (free|daily|breaking)",
    r"(follow|find) us (on|at) (twitter|facebook|instagram|social)",
    r"(click|tap) here to (subscribe|sign up|download|read more)",
    r"download (our|the) (free )?app",
    r"(news|email) (alert|newsletter|digest)",
    # 404·빈 페이지
    r"(page|content) (not found|unavailable|removed|deleted)",
    r"404 (error|not found)",
    r"(coming soon|under construction|temporarily unavailable)",
    # 한국어 스팸
    r"이 블로그는.{0,20}(폐쇄|종료|이전|닫|운영 중단)",
    r"(속보|일일|무료).{0,10}(이메일|앱|팟캐스트|뉴스레터).{0,20}(받으세요|신청|구독|다운로드)",
    r"(구독|알림|푸시).{0,10}(신청|설정|받기)",
    r"(앱|어플).{0,10}(다운로드|설치)",
    # 뉴스레터/요약 기사 (노이즈)
    r"^recap\b",
    r"good morning.{0,30}(reader|subscriber|viewer)",
    r"^world news in brief\b",
    r"^news in brief\b",
    r"^daily (recap|roundup|digest|briefing)\b",
    r"^(morning|evening|weekly) (brief|briefing|update|roundup)\b",
    # 광고성 문구
    r"(sponsored|advertisement|advertorial|paid content|promoted)",
    r"(privacy policy|cookie policy|terms of (use|service))$",
    # 편집자 주·재출판 고지가 기사 전체를 차지하는 경우
    r"^editor'?s?\s+(note|correction)\s*[:\-–].{0,400}(creative commons|license|republished|copyright)",
    r"^this article (was|has been) (republished|reprinted).{0,300}(creative commons|permission|license)",
    # 사설·칼럼·오피니언 — 뉴스가 아닌 의견 기사
    r"^\(?(editorial|opinion|commentary|column|op-?ed)\b",
    r"\bEDITORIAL from\b",
    r"^\(?사설\)?",
    r"^\(?칼럼\)?",
    r"^\(?논설\)?",
    r"^\(?기고\)?",
    # 통신사 슬러그 접두어 — 실제 제목이 아닌 메타 태그
    r"^\(\d+(st|nd|rd|th)\s+LD\)",
    r"^\(LEAD\)",
    r"^\(URGENT\)",
    r"^\(profile\)",
    r"^\(CORRECTED\)",
    # 연예/스포츠/문화 기사 차단 (사망·사고 키워드와 결합되어 오분류 방지)
    r"(actor|actress|singer|musician|rapper|comedian|celebrity|footballer|athlete).{0,80}(dies|died|dead|passes away|passed away)",
    r"(dies|died|dead|passed away).{0,80}(actor|actress|singer|musician|rapper|comedian|celebrity)",
    r"died aged \d+",
    r"dead at \d+",
    r"passes? away at \d+",
    r"(oscar|grammy|emmy|bafta|golden globe|cannes).{0,60}(winner|nominee|nominated|award)",
    r"(box office|film review|movie review|album review|concert|tour dates)",
    r"(fashion week|runway|supermodel|catwalk)",
    r"(premier league|nba|nfl|nhl|mlb|fifa|champions league|world cup).{0,60}(score|match|game|win|lose|draw|goal)",
    # 축제/카니발/전통 행사 — 오렌지 전투, 토마티나 등이 군사 이슈로 오분류되는 것 방지
    r"(carnival|festival|parade|annual tradition|celebration).{0,120}(battle|fight|throw|toss|hurl|pelt)",
    r"(orange|tomato|flower|food|fruit).{0,80}(battle|fight|throwing|toss|festival|carnival)",
    r"ivrea",           # 이탈리아 오렌지 전투 도시
    r"la tomatina",
    r"mardi gras",
    r"(rio|venice|nice|cologne|trinidad).{0,30}carnival",
    # ── 신규 소스 노이즈 필터 (소스 확장 Phase 1) ──
    r"(?i)\bsaudi.{0,30}(crown prince|royal|sport|entertainment)\b",
    r"(?i)\b(turkish football|super lig|galatasaray|fenerbahce|besiktas)\b",
    r"(?i)\b(recipe|cooking|lifestyle|fashion)\b",
    r"(?i)\b(book review|film review|album review)\b",
    r"(?i)\b(weather forecast|horoscope)\b",
    # K-pop / 엔터테인먼트 / 관광 노이즈
    r"(?i)\b(bts|bangtan|blackpink|exo|twice|nct|seventeen|stray kids|aespa|newjeans)\b",
    r"(?i)\b(le sserafim|enhypen|ateez|itzy|mamamoo|red velvet|got7|shinee)\b",
    r"(?i)\b(k-?pop|hallyu)\b.{0,60}\b(comeback|tour|concert|album|chart|fan|debut)\b",
    r"(?i)\b(idol|아이돌|컴백|팬미팅)\b.{0,60}\b(comeback|concert|album|tour|무대|stage)\b",
    # 미 국무부 여행경보 (상시 안내문, 뉴스 이벤트 아님)
    r"Level\s+\d+\s*:\s*(Exercise\s+(Increased\s+)?Caution|Reconsider\s+Travel|Do\s+Not\s+Travel)",
    # 텔레그램 해시태그 전용 포스트
    r"^#[A-Z]{2,10}(\s+#[A-Z]{2,10}){0,5}\s*$",
    # HTTP 에러 페이지가 기사로 수집된 경우
    r"Error\s+\d{3}\s+\(Server Error\)",
    r"^50[0-9]\s+(Internal\s+)?Server\s+Error",
]]

# 연예/스포츠 태그 집합 (RSS raw_metadata["tags"] 필터링용)
_ENTERTAINMENT_TAGS: set[str] = {
    "film", "movies", "television", "tv", "music", "celebrity", "entertainment",
    "fashion", "style", "arts", "culture", "sport", "sports", "football",
    "basketball", "baseball", "cricket", "tennis", "golf", "formula one",
    "obituaries", "obituary", "lifestyle", "food", "travel", "technology reviews",
    "books", "theater", "theatre", "dance", "comedy", "gaming",
    "k-pop", "kpop", "idol", "hallyu", "korean wave", "pop music",
}


def _is_spam(text: str) -> bool:
    """스팸/노이즈 텍스트 감지. True이면 수집 제외."""
    for pattern in _SPAM_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _is_entertainment_tag(tags: list[str]) -> bool:
    """RSS 태그가 연예/스포츠/문화 카테고리인지 판단."""
    for tag in tags:
        if tag.strip().lower() in _ENTERTAINMENT_TAGS:
            return True
    return False


def _is_quality_content(text: str) -> bool:
    """최소 품질 기준 충족 여부."""
    words = text.split()
    if len(words) < MIN_WORDS:
        return False
    if len(text) < MIN_CHARS:
        return False
    return True


# ── 본문 정제 ─────────────────────────────────────────────────────────────────

# 문장 단위로 제거할 홍보/CTA 패턴 (본문에 섞인 경우 문장만 제거)
_PROMO_SENTENCE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # ── 편집자 주 / 출처 고지 ─────────────────────────────────────────────────
    r"editor'?s?\s+(note|correction|update)\s*[:\-–]",
    r"this article (was|has been|is) (republished|reprinted|reposted|syndicated|originally published)",
    r"(republished|reprinted|reposted|syndicated) (with (permission|consent)|from|by|under)",
    r"(originally|first) (published|appeared|posted) (in|on|at|by)",
    r"this (story|article|piece|report) (was|is|has been) (first|originally|previously)",
    r"(this|the) article (is|was) (from|provided by|courtesy of|by)",
    r"(read|view|see) the (original|full) (article|story|post|version)",
    # ── Creative Commons / 라이선스 고지 ─────────────────────────────────────
    r"creative commons (license|licence|attribution)",
    r"(licensed|published|shared) under (a )?(creative commons|cc by|cc-by)",
    r"(cc\s*by|cc\s*nc|cc\s*sa|cc\s*nd)[\s\-][\d.]+",
    # ── 통신사 boilerplate ────────────────────────────────────────────────────
    r"^(ap|afp|reuters|bloomberg|bbc|guardian)\s*(reporting|report)\s*[:\-–]",
    r"(associated press|agence france-presse)\s*contributed",
    r"wire (service|story|report) (from|by|provided by)",
    # ── 저작권 표시 ───────────────────────────────────────────────────────────
    r"copyright\s+©?\s+\d{4}",
    r"©\s+\d{4}\s+\w",
    r"all rights reserved",
    r"(do not|may not) (reproduce|republish|redistribute)",
    # ── 개발 중 / 업데이트 고지 ──────────────────────────────────────────────
    r"this (is a )?developing story",
    r"this (story|article|post) (will be|has been|was) updated",
    r"(we will|we'll) update this (story|article|post)",
    # ── 독자 참여 유도 ────────────────────────────────────────────────────────
    r"(whatsapp|telegram|discord).{0,60}(join|subscribe|channel|가입|채널)",
    r"(to stay|to keep).{0,30}(up.to.date|updated|informed).{0,100}",
    r"(this investigation|this report).{0,30}(part of|collaboration|partnership)",
    r"(sign up|subscribe|join).{0,50}(here|now|today)",
    # ── 바이라인·날짜 단독 줄 ─────────────────────────────────────────────────
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b.{0,60}$",
    # ── CTA / 소셜 ───────────────────────────────────────────────────────────
    r"(click|tap|read more|see more|learn more).{0,30}(here|below|above|→|»)",
    r"(share|follow|like).{0,20}(this|us|our).{0,30}(story|article|page|account)",
    # ── 한국어 boilerplate ────────────────────────────────────────────────────
    r".{0,30}(채널|뉴스레터|이메일).{0,30}(구독|가입|신청).{0,60}",
    r"(편집자|기자)\s*(주|노트|코멘트)\s*[:\-：]",
    r"이 (기사|콘텐츠|글)는?.{0,30}(재게재|재배포|제공|출처)",
    r"크리에이티브 커먼즈.{0,30}라이선스",
    r"저작권.{0,20}\d{4}",
    r"무단 (전재|복제|배포|전용).{0,30}(금지|위반)",
]]


def _strip_promo_sentences(text: str) -> str:
    """본문에 섞인 홍보/프로모션 문장을 문장 단위로 제거."""
    # 마침표·느낌표·물음표 뒤 공백 기준으로 분리
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if any(p.search(sent) for p in _PROMO_SENTENCE_PATTERNS):
            continue
        clean.append(sent)
    return " ".join(clean).strip()


# ── 헬퍼 함수들 ──────────────────────────────────────────────────────────────

@dataclass
class RSSCollectResult:
    feed_url: str
    display_name: str
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)  # 저장된 raw_event ID 목록


def _compute_guid(entry: dict[str, Any]) -> str:
    """entry.id가 있으면 그대로, 없으면 link+published MD5 해시."""
    if entry.get("id"):
        return entry["id"][:256]
    raw = (entry.get("link", "") + entry.get("published", "")).encode("utf-8")
    if raw.strip():
        return hashlib.md5(raw).hexdigest()
    raw = (entry.get("title", "") + entry.get("published", "")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _fetch_og_image(article_url: str) -> str | None:
    """기사 페이지에서 og:image 메타 태그 추출 (RSS에 이미지가 없을 때 폴백)."""
    if not article_url or not article_url.startswith("http"):
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            article_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WeWantPeace/1.0)"},
        )
        resp = urllib.request.urlopen(req, timeout=3)
        # head만 읽기 (og:image는 <head> 안에 있으므로 처음 20KB면 충분)
        html = resp.read(20480).decode("utf-8", errors="ignore")
        # og:image 추출 (property="og:image" content="..." 또는 반대 순서)
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.IGNORECASE,
            )
        if m:
            url = m.group(1).strip()
            if url.startswith("http") and len(url) > 20:
                return url[:1024]
    except Exception:
        pass
    return None


def _extract_image_url(entry: dict[str, Any]) -> str | None:
    """RSS entry에서 대표 이미지 URL 추출. 우선순위: media_content → media_thumbnail → enclosures → 본문 img → 기사 og:image."""
    # 1. media_content (medium=image)
    for mc in entry.get("media_content", []):
        url = mc.get("url", "")
        if url and mc.get("medium") == "image":
            return url[:1024]
    # media_content에 medium 미지정이지만 image URL인 경우
    for mc in entry.get("media_content", []):
        url = mc.get("url", "")
        if url and re.search(r"\.(jpe?g|png|webp)", url, re.IGNORECASE):
            return url[:1024]
    # 2. media_thumbnail
    for mt in entry.get("media_thumbnail", []):
        url = mt.get("url", "")
        if url:
            return url[:1024]
    # 3. enclosures (type=image/*)
    for enc in entry.get("enclosures", []):
        url = enc.get("href", "") or enc.get("url", "")
        enc_type = enc.get("type", "")
        if url and enc_type.startswith("image/"):
            return url[:1024]
    # 4. 본문 HTML의 첫 <img src> (트래킹 픽셀 제외)
    content = ""
    if entry.get("content"):
        content = entry["content"][0].get("value", "")
    if not content:
        content = entry.get("summary", "")
    if content:
        for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE):
            url = m.group(1)
            # 트래킹 픽셀 제외: 1x1, pixel, tracking, beacon 등
            if re.search(r"(1x1|pixel|tracking|beacon|spacer|blank\.gif)", url, re.IGNORECASE):
                continue
            if url.startswith("http"):
                return url[:1024]
    # 5. 폴백: 기사 페이지의 og:image 메타 태그
    return _fetch_og_image(entry.get("link", ""))


def _extract_text(entry: dict[str, Any]) -> str:
    """entry에서 본문 텍스트 추출 후 홍보 문장 제거."""
    content = ""
    if entry.get("content"):
        content = entry["content"][0].get("value", "")
    if not content:
        content = entry.get("summary", "")
    if not content:
        content = entry.get("title", "")
    # HTML 태그 제거 + 다중 공백 정리
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"\s+", " ", content)
    content = content.strip()
    # 홍보/CTA 문장 제거
    content = _strip_promo_sentences(content)
    return content


def _parse_datetime(entry: dict[str, Any]) -> Optional[datetime]:
    """published_parsed 또는 updated_parsed → datetime. 파싱 실패 시 None."""
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            import time as time_mod
            return datetime.fromtimestamp(time_mod.mktime(t), tz=timezone.utc)
    except Exception:
        pass
    return None


# ── 수집기 ───────────────────────────────────────────────────────────────────

class RSSCollector:
    """RSS/Atom 피드 파서."""

    # 연속 에러 N회 초과 시 자동 비활성화
    MAX_CONSECUTIVE_ERRORS = 10

    async def _track_error(self, redis, source: SourceChannel, db: AsyncSession, error_msg: str):
        """연속 에러 카운트 추적. MAX_CONSECUTIVE_ERRORS 초과 시 자동 비활성화."""
        if redis is None:
            return
        err_key = f"rss:consecutive_errors:{source.id}"
        try:
            count = await redis.incr(err_key)
            await redis.expire(err_key, 86400 * 7)  # 7일 TTL
            if count >= self.MAX_CONSECUTIVE_ERRORS:
                source.is_active = False
                db.add(source)
                await db.flush()
                await redis.delete(err_key)
                logger.warning(
                    "RSS 피드 자동 비활성화: %s (%s) — 연속 %d회 에러",
                    source.display_name, source.feed_url, count,
                )
        except Exception as e:
            logger.warning("Redis 에러 카운트 실패 (%s): %s", source.display_name, e)

    async def _reset_error_count(self, redis, source: SourceChannel):
        """수집 성공 시 연속 에러 카운트 초기화."""
        if redis is None:
            return
        try:
            await redis.delete(f"rss:consecutive_errors:{source.id}")
        except Exception:
            pass

    async def collect_feed(
        self,
        source: SourceChannel,
        db: AsyncSession,
        redis=None,
    ) -> RSSCollectResult:
        """
        source.feed_url에서 RSS를 파싱하여 raw_events에 저장.
        - feedparser는 asyncio.to_thread()로 블로킹 해소
        - 스팸·품질 필터 적용
        - URL 리다이렉트 감지 시 feed_url 자동 갱신
        - 404/410 시 자동 비활성화
        - 연속 에러 10회 시 자동 비활성화
        """
        result = RSSCollectResult(
            feed_url=source.feed_url or "",
            display_name=source.display_name,
        )

        if not source.feed_url:
            result.errors.append("feed_url 없음")
            return result

        try:
            # feedparser.parse()는 동기 블로킹 → 스레드풀에서 실행 (30초 타임아웃)
            parsed = await asyncio.wait_for(
                asyncio.to_thread(feedparser.parse, source.feed_url),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            result.errors.append(f"피드 타임아웃 (30s): {source.feed_url}")
            await self._track_error(redis, source, db, "timeout")
            return result
        except Exception as e:
            result.errors.append(f"피드 파싱 오류: {e}")
            await self._track_error(redis, source, db, str(e))
            return result

        # HTTP 상태 확인: 404/410 → 연속 3회 이상 시 자동 비활성화
        http_status = getattr(parsed, "status", 200)
        if http_status in (404, 410):
            not_found_key = f"rss:not_found:{source.id}"
            not_found_count = 0
            if redis is not None:
                try:
                    not_found_count = await redis.incr(not_found_key)
                    await redis.expire(not_found_key, 86400 * 3)  # 3일 TTL
                except Exception as e:
                    logger.warning("Redis 404 카운트 실패 (%s): %s", source.display_name, e)
                    not_found_count = 1

            if not_found_count >= 3:
                source.is_active = False
                db.add(source)
                await db.flush()
                if redis is not None:
                    try:
                        await redis.delete(not_found_key)
                    except Exception:
                        pass
                logger.warning(
                    "RSS 피드 자동 비활성화 (HTTP %d, 연속 %d회): %s (%s)",
                    http_status, not_found_count, source.display_name, source.feed_url,
                )
                result.errors.append(f"HTTP {http_status} — 연속 {not_found_count}회, 자동 비활성화")
            else:
                logger.warning(
                    "RSS 피드 HTTP %d 감지 (%d/3회): %s (%s)",
                    http_status, not_found_count, source.display_name, source.feed_url,
                )
                result.errors.append(f"HTTP {http_status} — 연속 {not_found_count}/3회")
            return result

        # URL 리다이렉트 감지: 최종 URL이 다르면 feed_url 자동 갱신
        final_url = getattr(parsed, "href", None)
        if final_url and final_url != source.feed_url and parsed.entries:
            logger.info(
                "RSS 피드 URL 자동 갱신: %s — %s → %s",
                source.display_name, source.feed_url, final_url,
            )
            source.feed_url = final_url
            db.add(source)
            await db.flush()

        if parsed.bozo and not parsed.entries:
            result.errors.append(f"피드 오류: {parsed.bozo_exception}")
            await self._track_error(redis, source, db, str(parsed.bozo_exception))
            return result

        # bozo=True이지만 entries가 있으면 마이너 XML 오류 → 에러 카운트 증가 없이 정상 처리
        if parsed.bozo and parsed.entries:
            logger.debug(
                "RSS 피드 마이너 XML 오류 (무시): %s — %s",
                source.display_name, parsed.bozo_exception,
            )

        # 정상 수집 도달 → 에러 카운트 초기화
        await self._reset_error_count(redis, source)

        for entry in parsed.entries:
            guid = _compute_guid(entry)
            text = _extract_text(entry)
            entry_tags = [t.get("term", "") for t in entry.get("tags", [])]

            # 1. 품질 필터
            if not _is_quality_content(text):
                result.skipped += 1
                continue

            # 2. 엔터테인먼트/스포츠 태그 필터 (연예인·스포츠 기사 차단)
            if _is_entertainment_tag(entry_tags):
                logger.debug("엔터 태그 필터: %s — %s", source.display_name, text[:80])
                result.skipped += 1
                continue

            # 3. 스팸 필터 (제목+본문 대상)
            title_text = entry.get("title", "") + " " + text
            if _is_spam(title_text):
                logger.debug("스팸 필터: %s — %s", source.display_name, text[:80])
                result.skipped += 1
                continue

            # 3. 중복 확인 (피드별 commit으로 pending INSERT 수 제한됨)
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "rss",
                    RawEvent.external_id == guid,
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            collected_at = datetime.now(timezone.utc)
            event_time = _parse_datetime(entry) or collected_at
            image_url = _extract_image_url(entry)
            raw_metadata = {
                "title": entry.get("title", "")[:512],
                "link": entry.get("link", ""),
                "author": entry.get("author", ""),
                "tags": [t.get("term", "") for t in entry.get("tags", [])],
                "published": event_time.isoformat(),  # 실제 발행 시간 (정규화에서 사용)
                "time_source": "parsed" if _parse_datetime(entry) else "collected_at",
            }
            if image_url:
                raw_metadata["image_url"] = image_url

            raw_event = RawEvent(
                source_channel_id=source.id,
                source_type="rss",
                external_id=guid,
                raw_text=text[:10000],
                raw_metadata=raw_metadata,
                lang=None,
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)  # flush 후 ID 확보용
            result.collected += 1

        # flush는 호출하지 않음 — caller(collect_all)에서 일괄 commit 처리
        # (asyncio.gather로 동시 실행 시 "Session is already flushing" 방지)
        return result

    async def collect_all(self, db: AsyncSession, redis=None) -> list[RSSCollectResult]:
        """
        모든 활성 RSS 소스에서 수집.
        Semaphore(5)로 동시 HTTP 요청 수 제한.
        """
        stmt = select(SourceChannel).where(
            SourceChannel.is_active == True,
            SourceChannel.source_type == "rss",
        )
        channels_result = await db.execute(stmt)
        channels: list[SourceChannel] = list(channels_result.scalars().all())

        if not channels:
            logger.info("활성 RSS 채널 없음")
            return []

        # 동시 요청 최대 5개 제한
        sem = asyncio.Semaphore(5)

        # 세션 공유 안전성을 위해 순차 실행 (asyncio.gather 대신)
        # 피드별 flush+commit — 하나 실패해도 나머지는 저장됨
        results = []
        for ch in channels:
            async with sem:
                try:
                    result = await self.collect_feed(ch, db, redis=redis)
                    # Per-feed flush+commit — 피드별로 DB에 즉시 저장
                    if result.collected > 0:
                        try:
                            await db.flush()
                            await db.commit()
                        except Exception as db_err:
                            await db.rollback()
                            logger.error(
                                "RSS 피드 %s DB 저장 실패: %s",
                                ch.display_name, db_err,
                            )
                            result.errors.append(f"DB 저장 실패: {db_err}")
                            result.collected = 0
                            result.raw_event_ids.clear()
                    logger.info(
                        "RSS 수집 완료: %s (collected=%d, skipped=%d, errors=%s)",
                        ch.display_name,
                        result.collected,
                        result.skipped,
                        result.errors,
                    )
                    results.append(result)
                    # Redis에 채널별 수집 상태 저장
                    status = "error" if result.errors else "ok"
                    await self._save_collect_status(
                        redis, ch.id, status, result.collected, result.skipped,
                        "; ".join(result.errors),
                    )
                except Exception as e:
                    logger.error("RSS 채널 %s 수집 오류: %s", ch.display_name, e)
                    # 세션이 rollback 상태일 수 있으므로 복구
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    results.append(
                        RSSCollectResult(
                            feed_url=ch.feed_url or "",
                            display_name=ch.display_name,
                            errors=[str(e)],
                        )
                    )
                    await self._save_collect_status(
                        redis, ch.id, "error", 0, 0, str(e),
                    )
        return results

    @staticmethod
    async def _save_collect_status(
        redis, channel_id: int, status: str,
        collected: int, skipped: int, error: str = "",
    ):
        """Redis에 채널별 수집 상태 저장 (TTL 1시간)."""
        if redis is None:
            return
        try:
            key = f"collect:status:{channel_id}"
            value = json.dumps({
                "status": status,
                "collected": collected,
                "skipped": skipped,
                "error": error,
                "last_collected_at": datetime.now(timezone.utc).isoformat(),
            })
            await redis.set(key, value, ex=3600)
        except Exception as e:
            logger.warning("Redis 수집 상태 저장 실패 (channel=%s): %s", channel_id, e)
