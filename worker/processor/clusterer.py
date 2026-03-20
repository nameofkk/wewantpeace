"""
EventClusterer: 24시간 윈도우 기반 이슈 클러스터링.

클러스터 키: {country_code}:{topic} 또는 {geohash4}:{topic}
같은 키 + Filtered Jaccard 유사도 검사 → 서브토픽별 분리.

Filtered Jaccard: 국가명/토픽 키워드를 제거한 후 콘텐츠 단어만으로
유사도 계산 → 같은 country:topic 버킷에서 다른 사건의 오병합 방지.
경계 영역(0.10~0.20)에서는 GPT-4o-mini AI 판정으로 보완.
"""
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
from worker.processor.trending_engine import _calc_kscore
from worker.processor.ai_title import generate_ai_title

logger = logging.getLogger(__name__)

WINDOW_MINUTES = 1440  # 24시간 — 국제 뉴스 시차 고려, Filtered Jaccard로 오병합 방지
MAX_CLUSTER_AGE_HOURS = 120  # 클러스터 절대 수명 상한 — 72→120h, 주요 이벤트는 5일간 지속

# geohash 없는 버킷("0000:topic")의 최대 이벤트 수 — 초과 시 새 클러스터 생성
MAX_EVENTS_UNKNOWN_GEO = 2

# 클러스터당 최대 이벤트 수 — 초과 시 새 클러스터 생성
MAX_EVENTS_PER_CLUSTER = 50

# 제목 유사도 임계값 (Filtered Jaccard 기준 — 노이즈 단어 제거 후)
MIN_TITLE_OVERLAP = 0.12           # 0.15→0.12, 필터링 후 잔존 단어가 적어 더 낮은 임계값 필요
MIN_TITLE_OVERLAP_HIGH_SEV = 0.08  # 0.13→0.08, 고심각도 이벤트는 더 적극적으로 병합
# AI 판정 경계 영역: 이 구간에서만 GPT-4o-mini로 "같은 사건?" 확인
AI_MATCH_LOW = 0.06   # 0.10→0.06, 더 많은 경계 케이스를 AI에게 위임
AI_MATCH_HIGH = 0.25  # 0.20→0.25, AI 판정 상한 확장

# Sub-topic soft signal 보정값
SUBTOPIC_BONUS = 0.06    # 같은 sub_topic (둘 다 non-general) → sim +0.06
SUBTOPIC_PENALTY = 0.08  # 다른 sub_topic (둘 다 non-general) → sim -0.08

# 활성 클러스터 후보 최대 조회 수
MAX_CANDIDATE_CLUSTERS = 10

# ── 제목 유사도 (스테밍 + 이중 언어) ──────────────────────────────────────────

_STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "to", "of", "and", "or",
    "is", "are", "was", "were", "has", "have", "had", "for", "with",
    "that", "this", "it", "its", "by", "be", "as", "not", "but",
    "from", "after", "how", "what", "who", "why", "will", "says",
    "say", "said", "new", "been", "more", "over", "amid", "into",
})

# 국가 형용사 → 국가명 정규화
_DEMONYM_TO_STEM: dict[str, str] = {
    "russian": "russia", "russians": "russia",
    "iranian": "iran", "iranians": "iran",
    "israeli": "israel", "israelis": "israel",
    "american": "america", "americans": "america",
    "ukrainian": "ukraine", "ukrainians": "ukraine",
    "chinese": "china",
    "turkish": "turkey", "turks": "turkey", "türkiye": "turkey",
    "indian": "india", "indians": "india",
    "syrian": "syria", "syrians": "syria",
    "iraqi": "iraq", "iraqis": "iraq",
    "palestinian": "palestine", "palestinians": "palestine",
    "finnish": "finland", "finns": "finland",
    "yemeni": "yemen", "yemenis": "yemen",
    "lebanese": "lebanon",
    "pakistani": "pakistan", "pakistanis": "pakistan",
    "somali": "somalia", "somalis": "somalia",
    "sudanese": "sudan",
    "ethiopian": "ethiopia", "ethiopians": "ethiopia",
    "afghan": "afghanistan", "afghans": "afghanistan",
    "japanese": "japan",
    "korean": "korea", "koreans": "korea",
    "british": "britain", "brits": "britain",
    "french": "france",
    "german": "germany", "germans": "germany",
    "italian": "italy", "italians": "italy",
    "spanish": "spain",
    "egyptian": "egypt", "egyptians": "egypt",
    "saudi": "saudiarabia", "saudis": "saudiarabia",
    "kuwaiti": "kuwait", "kuwaitis": "kuwait",
    "emirati": "uae", "emiratis": "uae",
    "bahraini": "bahrain", "bahrainis": "bahrain",
    "qatari": "qatar", "qataris": "qatar",
    "omani": "oman", "omanis": "oman",
}


# ── Filtered Jaccard: 국가명/토픽 단어 필터 ────────────────────────────────
# cluster_key(country:topic)에 이미 반영된 정보를 Jaccard에서 제외하여
# 콘텐츠 유사도만 정확히 측정 → 오병합 방지 + 정당한 병합 허용

_COUNTRY_STEMS: frozenset[str] = frozenset({
    "iran", "iraq", "israel", "syria", "russia", "ukraine", "china", "turkey",
    "yemen", "lebanon", "pakistan", "somalia", "sudan", "ethiopia", "afghanistan",
    "korea", "egypt", "india", "palestine", "america", "britain", "france",
    "germany", "japan", "brazil", "mexico", "haiti", "venezuela", "libya",
    "nigeria", "taiwan", "myanmar", "cuba", "uae", "qatar", "bahrain", "kuwait",
    "oman", "saudiarabia", "finland",
})

_TOPIC_FILTER_STEMS: frozenset[str] = frozenset({
    # conflict — "arm"/"forc" 제거 (너무 공격적: "armed convoy" vs "forced evacuation" 구분 불가)
    "conflict", "war", "milit",
    # terror
    "terror", "violen", "extrem",
    # coup
    "coup", "overthrow",
    # sanctions
    "sanction", "embargo",
    # cyber
    "cyber", "hack",
    # protest
    "protest", "demonstrat",
    # diplomacy
    "diplomacy", "diplomat",
    # maritime
    "maritim", "naval",
    # disaster
    "disast",
    # health
    "health", "pandem", "epidem",
    # generic news words (클러스터 키와 무관하지만 모든 뉴스에 나타나서 가짜 유사도 생성)
    "govern", "offici", "report", "state", "minist", "presid",
})


def _stem_word(w: str) -> str:
    """영어 단어 기본 스테밍: 국가 형용사 통일 + 접미사 제거."""
    if w in _DEMONYM_TO_STEM:
        return _DEMONYM_TO_STEM[w]
    if len(w) > 4:
        if w.endswith("ies"):
            return w[:-3] + "y"
        if w.endswith("ing"):
            return w[:-3]
        if w.endswith("ed") and not w.endswith("eed"):
            return w[:-2]
        if w.endswith("es"):
            return w[:-2]
        if w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
    return w


def _stemmed_en_words(text: str) -> set[str]:
    """영어 제목에서 스테밍된 단어 집합 추출."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return {_stem_word(w) for w in tokens if w not in _STOP_WORDS and len(w) > 2}


def _ko_words(text: str) -> set[str]:
    """한국어 제목에서 2글자 이상 단어 집합 추출."""
    tokens = re.findall(r"[가-힣]+", text)
    return {w for w in tokens if len(w) >= 2}


def _filtered_en_words(text: str) -> set[str]:
    """국가명/토픽 키워드 제거 후 콘텐츠 단어만 추출 (Filtered Jaccard용)."""
    words = _stemmed_en_words(text)
    return {w for w in words if w not in _COUNTRY_STEMS and w not in _TOPIC_FILTER_STEMS}


def _title_similarity(
    en_a: str, en_b: str,
    ko_a: str | None = None, ko_b: str | None = None,
) -> float:
    """
    두 제목의 Filtered Jaccard 유사도 (0.0 ~ 1.0).

    영어: 국가명/토픽 단어를 제거한 Filtered Jaccard (콘텐츠 유사도만 측정).
    한국어: 기존 Jaccard 유지.
    max(영어, 한국어) 반환.

    Filtered Jaccard가 기존 Jaccard보다 나은 이유:
    - "Iran nuclear talks" vs "Iran missile strikes" → 기존: 0.11 (iran 공유) → 필터: 0.00 (분리)
    - "Syria Aleppo fighting" vs "Fighting in Aleppo" → 기존: 0.14 → 필터: 0.50 (병합)
    """
    # Filtered Jaccard (영어)
    a_filt = _filtered_en_words(en_a)
    b_filt = _filtered_en_words(en_b)
    en_sim = (len(a_filt & b_filt) / len(a_filt | b_filt)) if (a_filt and b_filt) else 0.0

    # 한국어 Jaccard
    ko_sim = 0.0
    if ko_a and ko_b:
        a_ko = _ko_words(ko_a)
        b_ko = _ko_words(ko_b)
        if a_ko and b_ko:
            ko_sim = len(a_ko & b_ko) / len(a_ko | b_ko)

    return max(en_sim, ko_sim)

# ── AI 클러스터 매칭 (경계 영역 보완) ─────────────────────────────────────────

_AI_MATCH_PROMPT = """\
You are a news event deduplication classifier.
Given two news headlines about the same country and topic, determine if they describe the SAME specific event/incident or DIFFERENT events.

Rules:
- SAME = same incident, just reported by different outlets or at different times
- DIFFERENT = different incidents, even if in the same country/topic category
- Focus on specific details: location, actors, timing, nature of event
- Respond ONLY with JSON: {"same": true} or {"same": false}"""


@lru_cache(maxsize=256)
def _ai_same_event(
    title_a: str,
    title_b: str,
    topic: str,
    country_code: str | None,
) -> bool | None:
    """
    GPT-4o-mini로 두 제목이 같은 사건인지 판정 (경계 영역에서만 호출).
    LRU 캐시로 동일 쌍 중복 호출 방지.

    Returns: True(같은 사건), False(다른 사건), None(API 실패)
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None

    user_msg = f"Country: {country_code or 'Unknown'}\nTopic: {topic}\n\nHeadline A: {title_a[:200]}\nHeadline B: {title_b[:200]}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _AI_MATCH_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=30,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        result = data.get("same", False)
        logger.debug("AI 매칭 판정: %s vs %s → %s", title_a[:40], title_b[:40], result)
        return bool(result)
    except Exception:
        logger.warning("AI 매칭 판정 실패, 폴백 (분리)")
        return None


# ── 클러스터 제목 생성 ────────────────────────────────────────────────────────

_TOPIC_LABELS_KO: dict[str, str] = {
    "conflict":  "무장 충돌",
    "terror":    "폭력·테러",
    "coup":      "정변·쿠데타",
    "sanctions": "경제 제재",
    "cyber":     "사이버 공격",
    "protest":   "시위·집회",
    "diplomacy": "외교",
    "maritime":  "해상 분쟁",
    "disaster":  "재난·재해",
    "health":    "감염병·보건",
    "unknown":   "이슈",
}

_COUNTRY_NAMES_KO: dict[str, str] = {
    "US": "미국", "UA": "우크라이나", "RU": "러시아",
    "PS": "팔레스타인", "IL": "이스라엘", "IR": "이란",
    "CN": "중국", "KP": "북한", "KR": "한국", "TW": "대만",
    "SY": "시리아", "MM": "미얀마", "SD": "수단", "ET": "에티오피아",
    "SO": "소말리아", "VE": "베네수엘라", "HT": "아이티",
    "LB": "레바논", "IQ": "이라크", "AF": "아프가니스탄",
    "PK": "파키스탄", "IN": "인도", "MX": "멕시코",
    "GB": "영국", "FR": "프랑스", "DE": "독일",
    "JP": "일본", "BR": "브라질", "AU": "호주",
    "TR": "터키", "SA": "사우디", "YE": "예멘",
    "LY": "리비아", "NG": "나이지리아", "ML": "말리",
    # ── 추가 국가 ────────────────────────────────────────────────────────────
    "IT": "이탈리아", "ES": "스페인", "PT": "포르투갈",
    "NL": "네덜란드", "BE": "벨기에", "SE": "스웨덴",
    "NO": "노르웨이", "DK": "덴마크", "CH": "스위스",
    "AT": "오스트리아", "GR": "그리스", "CZ": "체코",
    "HU": "헝가리", "PL": "폴란드", "RO": "루마니아",
    "RS": "세르비아", "HR": "크로아티아", "EE": "에스토니아",
    "FI": "핀란드", "CA": "캐나다", "NZ": "뉴질랜드",
    "ZA": "남아공", "KE": "케냐", "GH": "가나",
    "MA": "모로코", "DZ": "알제리", "EG": "이집트",
    "TH": "태국", "VN": "베트남", "ID": "인도네시아",
    "MY": "말레이시아", "SG": "싱가포르", "PH": "필리핀",
    "BD": "방글라데시", "CO": "콜롬비아", "PE": "페루",
    "CL": "칠레", "AR": "아르헨티나", "BO": "볼리비아",
    "EC": "에콰도르", "UG": "우간다", "SN": "세네갈",
}


@lru_cache(maxsize=512)
def _translate_cached(text: str) -> str | None:
    """번역 결과 캐시 (동일 텍스트 중복 번역 방지)."""
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="ko").translate(text[:200])
    except Exception:
        return None


def _is_junk_title(title: str) -> bool:
    """해시태그만 있거나 의미 없는 제목인지 판별."""
    # 해시태그 + 이모지(국기 포함) + 특수문자 제거
    stripped = re.sub(r'#\S+', '', title)
    stripped = re.sub(
        '[\U0001F1E0-\U0001F1FF\U0001F000-\U0001FFFF\u2600-\u27BF'
        '\uFE00-\uFE0F\u200D\u20E3\U000E0020-\U000E007F'
        '⚡️🔴🟠🟡🟢⚠️🚨📰💥🔥❗️‼️]',
        '', stripped,
    ).strip()
    # 제거 후 남은 글자가 너무 짧으면 쓰레기 제목
    # 한국어 포함 시 5자, 영어만일 때 8자 (도시명만 남는 케이스 방지)
    has_ko = bool(re.search(r'[가-힣]', stripped))
    min_len = 5 if has_ko else 8
    if len(stripped) < min_len:
        return True
    low = stripped.lower()
    # 인사 패턴
    if re.match(r'^(good\s+(morning|afternoon|evening)|좋은\s+(아침|오후|저녁))', low):
        return True
    # 뉴스 메타 패턴 — 내용 없이 형식만 있는 제목
    if re.match(
        r'^(afternoon|morning|evening|daily|weekly|overnight)\s*'
        r'(recap|summary|update|brief|briefing|roundup|round-up|report|digest|wrap)',
        low,
    ):
        return True
    if re.match(r'^(live|breaking)\s*(briefing|update|blog)\s*[:.]?\s*$', low):
        return True
    if re.match(r'^(오후|오전|아침|저녁|주간|일일)\s*(요약|브리핑|업데이트|정리|리포트)\s*$', low):
        return True
    # "국가명 + 토픽라벨"만 있는 2단어 제목 (예: "China Diplomacy", "Lebanon Disaster")
    _topic_words = {
        'conflict', 'diplomacy', 'sanctions', 'disaster', 'protest',
        'coup', 'crisis', 'dispute', 'attack', 'strikes', 'terror',
    }
    words = low.split()
    if len(words) <= 2:
        if any(w in _topic_words for w in words):
            return True
    # EDITORIAL / opinion 전용 접두사
    if re.match(r'^\(?(editorial|opinion|column|사설|칼럼)', low):
        return True
    # 날짜/도시만 있는 패턴 (예: "Tehran 20 February 2026 #1")
    date_stripped = re.sub(r'\d+', '', stripped).strip()
    date_stripped = re.sub(r'(january|february|march|april|may|june|july|august|'
                           r'september|october|november|december)', '', date_stripped,
                           flags=re.IGNORECASE).strip()
    has_ko_date = bool(re.search(r'[가-힣]', date_stripped))
    min_len_date = 5 if has_ko_date else 8
    if len(date_stripped) < min_len_date:
        return True
    return False


_TOPIC_LABELS_EN: dict[str, str] = {
    "conflict": "Conflict", "terror": "Terror Attack", "coup": "Coup",
    "sanctions": "Sanctions", "cyber": "Cyber Attack", "protest": "Protest",
    "diplomacy": "Diplomacy", "maritime": "Maritime Dispute",
    "disaster": "Disaster", "health": "Health Crisis", "unknown": "Issue",
}

_COUNTRY_NAMES_EN: dict[str, str] = {
    "US": "US", "UA": "Ukraine", "RU": "Russia", "PS": "Palestine",
    "IL": "Israel", "IR": "Iran", "CN": "China", "KP": "North Korea",
    "KR": "South Korea", "TW": "Taiwan", "SY": "Syria", "MM": "Myanmar",
    "SD": "Sudan", "ET": "Ethiopia", "SO": "Somalia", "VE": "Venezuela",
    "HT": "Haiti", "LB": "Lebanon", "IQ": "Iraq", "AF": "Afghanistan",
    "PK": "Pakistan", "IN": "India", "MX": "Mexico", "GB": "UK",
    "FR": "France", "DE": "Germany", "JP": "Japan", "BR": "Brazil",
    "TR": "Turkey", "SA": "Saudi Arabia", "YE": "Yemen", "LY": "Libya",
    "NG": "Nigeria", "CU": "Cuba", "AE": "UAE", "QA": "Qatar",
    "BH": "Bahrain", "KW": "Kuwait", "EG": "Egypt",
}


def _make_fallback_titles(
    topic: str,
    country_code: str | None,
) -> tuple[str, str]:
    """쓰레기 제목용 국가+토픽 폴백 (en, ko) 반환."""
    topic_ko = _TOPIC_LABELS_KO.get(topic, "이슈")
    topic_en = _TOPIC_LABELS_EN.get(topic, "Issue")
    country_ko = _COUNTRY_NAMES_KO.get(country_code or "", "")
    country_en = _COUNTRY_NAMES_EN.get(country_code or "", country_code or "")

    if country_ko:
        return f"{country_en} {topic_en}", f"{country_ko} {topic_ko}"
    return topic_en, topic_ko


def _make_cluster_title_ko(
    title: str,
    topic: str,
    country_code: str | None,
) -> str | None:
    """
    클러스터 홈 카드용 한국어 제목 생성.
    해시태그만 있는 저품질 제목은 국가+토픽 폴백 제목 생성.
    """
    if _is_junk_title(title):
        _, title_ko = _make_fallback_titles(topic, country_code)
        return title_ko

    title_ko = _translate_cached(title)
    if title_ko is None:
        logger.debug("한국어 번역 실패: %s", title[:50])
        return None

    short = title_ko.strip()
    if not short:
        return None

    # 70자 초과 시 자르기
    if len(short) > 70:
        short = short[:68] + "…"
    return short


def _cluster_key(event: "NormalizedEvent") -> str:
    """
    클러스터 키 생성 전략 (우선순위):
    1. country_code 있으면 → {country_code}:{topic}  (국가별 격리)
    2. geohash 4자리 있으면 → {geohash4}:{topic}  (좌표만 있는 경우)
    3. 없으면 → 0000:{topic}

    이전 버전은 geohash4를 우선해서 다른 나라 이벤트가
    같은 geohash 버킷에 혼입되는 문제가 있었음 (dqcj:diplomacy 등).
    국가 코드를 항상 우선하고, 같은 국가 내 다른 이슈는
    title_overlap 검사로 분리한다.
    """
    if event.country_code:
        return f"{event.country_code}:{event.topic}"
    geo4 = (event.geohash5 or "")[:4]
    if geo4:
        return f"{geo4}:{event.topic}"
    return f"0000:{event.topic}"


async def assign_cluster(
    event: NormalizedEvent,
    db: AsyncSession,
    *,
    skip_ai: bool = False,
) -> tuple[IssueCluster | None, bool]:
    """
    NormalizedEvent를 24시간 윈도우 내 같은 cluster_key의 IssueCluster에 할당.
    없으면 새 클러스터 생성.

    Filtered Jaccard + AI 경계 판정:
    - sim >= threshold  → 무조건 병합
    - AI_MATCH_LOW <= sim < threshold → GPT-4o-mini로 "같은 사건?" 판정
    - sim < AI_MATCH_LOW → 무조건 분리

    Args:
        skip_ai: True면 AI 판정 건너뜀 (재클러스터링 배치에서 비용 절약)

    Returns:
        (IssueCluster | None, just_verified: bool)

    severity < 20 또는 topic="unknown" + severity < 25이면 (None, False) 반환 (잡음 제거).
    """
    # 잡음 필터: 연예·스포츠 등 낮은 severity 이벤트 제외
    if event.severity < 20:
        return None, False
    if event.topic == "unknown" and event.severity <= 25:
        return None, False

    geohash5 = event.geohash5 or "00000"
    key = _cluster_key(event)
    window_cutoff = event.event_time - timedelta(minutes=WINDOW_MINUTES)

    # 윈도우 내 활성 클러스터 전체 조회 → 제목 유사도로 최적 매칭
    result = await db.execute(
        select(IssueCluster).where(
            IssueCluster.cluster_key == key,
            IssueCluster.window_end >= event.event_time,
        ).order_by(IssueCluster.last_event_at.desc()).limit(MAX_CANDIDATE_CLUSTERS)
    )
    candidates = list(result.scalars().all())
    now = datetime.now(timezone.utc)

    # ── 후보 클러스터 중 최적 매칭 선택 ──────────────────────────────────────
    cluster: IssueCluster | None = None
    best_sim = -1.0
    # AI 경계 판정 후보: (sim, candidate) — 임계값 미만이지만 AI_MATCH_LOW 이상
    ai_candidates: list[tuple[float, IssueCluster]] = []

    for cand in candidates:
        no_country = not event.country_code
        no_geo = not event.geohash5

        # (0a) 클러스터 절대 수명 상한: window_start 기준 72시간 초과 시 매칭 제외
        if cand.window_start and (event.event_time - cand.window_start).total_seconds() > MAX_CLUSTER_AGE_HOURS * 3600:
            continue

        # (0b) 대형 클러스터 상한: 이벤트 50개 초과 시 매칭 제외
        if cand.event_count >= MAX_EVENTS_PER_CLUSTER:
            continue

        # (1) 지오/국가 미분류 버킷이 MAX_EVENTS 초과 → 이 후보 건너뛰기
        if no_country and no_geo and cand.event_count >= MAX_EVENTS_UNKNOWN_GEO:
            continue

        # (2) Filtered Jaccard 유사도 계산
        sim = _title_similarity(
            event.title, cand.title,
            ko_a=getattr(event, "title_ko", None),
            ko_b=cand.title_ko,
        )

        # (2b) Sub-topic soft signal 보정
        ev_sub = getattr(event, "sub_topic", "general") or "general"
        cand_sub = getattr(cand, "sub_topic", "general") or "general"
        if ev_sub != "general" and cand_sub != "general":
            if ev_sub == cand_sub:
                sim += SUBTOPIC_BONUS
            else:
                sim -= SUBTOPIC_PENALTY

        # 고심각도(양쪽 모두 >=50)는 낮은 임계값, 일반은 높은 임계값
        threshold = MIN_TITLE_OVERLAP_HIGH_SEV \
            if event.severity >= 50 and cand.severity >= 50 \
            else MIN_TITLE_OVERLAP

        if sim >= threshold and sim > best_sim:
            best_sim = sim
            cluster = cand
        elif not skip_ai and AI_MATCH_LOW <= sim < threshold:
            # 경계 영역: AI 판정 후보로 등록
            ai_candidates.append((sim, cand))

    # ── AI 경계 판정: 임계값 미만이지만 AI가 "같은 사건"이라 판단하면 병합 ──
    if cluster is None and ai_candidates:
        # 유사도 높은 순으로 AI 판정 (최대 2개만 — 비용 절약)
        ai_candidates.sort(key=lambda x: x[0], reverse=True)
        for sim, cand in ai_candidates[:2]:
            ai_result = _ai_same_event(
                event.title, cand.title,
                event.topic, event.country_code,
            )
            if ai_result is True:
                cluster = cand
                best_sim = sim
                logger.info(
                    "AI 매칭 승인: event=%s → cluster=%s (sim=%.3f)",
                    event.title[:40], cand.title[:40], sim,
                )
                break

    if cluster:
        logger.debug(
            "클러스터 매칭: event=%s → cluster=%s (sim=%.3f, candidates=%d)",
            event.title[:40], cluster.title[:40], best_sim, len(candidates),
        )

    if cluster:
        n = cluster.event_count
        cluster.event_count = n + 1
        cluster.last_event_at = event.event_time
        cluster.window_end = event.event_time + timedelta(minutes=WINDOW_MINUTES)
        # confidence: 이동 평균
        cluster.confidence = round(
            (cluster.confidence * n + event.confidence) / (n + 1), 3
        )
        # severity: 최대값 유지
        if event.severity > cluster.severity:
            cluster.severity = event.severity
        # independent_sources: trending_engine에서 실제 독립출처 수로 갱신
        # (여기서는 source_channel 중복 확인 불가 → 5분 주기 배치에서 정확히 계산)
        # source_tiers: 새 tier 추가
        if event.source_tier:
            existing = list(cluster.source_tiers or [])
            existing.append(event.source_tier)
            cluster.source_tiers = existing
        # 제목 승격: 현재 제목이 쓰레기이고 새 이벤트 제목이 더 나으면 교체
        if _is_junk_title(cluster.title) and not _is_junk_title(event.title):
            ai = generate_ai_title(
                [{"title": event.title, "body": event.body or ""}, {"title": cluster.title}],
                event.topic, event.country_code or cluster.country_code,
            )
            if ai:
                cluster.title, cluster.title_ko = ai
            else:
                cluster.title = event.title
                cluster.title_ko = _make_cluster_title_ko(
                    event.title, event.topic, event.country_code or cluster.country_code,
                )
            logger.info("클러스터 제목 승격: %s → %s", cluster.cluster_key, cluster.title[:50])
        # 제목은 괜찮은데 title_ko가 없으면 재생성 시도
        elif cluster.title_ko is None and not _is_junk_title(cluster.title):
            ai = generate_ai_title(
                [{"title": cluster.title, "body": event.body or ""}],
                cluster.topic, cluster.country_code,
            )
            if ai:
                cluster.title, cluster.title_ko = ai
            else:
                cluster.title_ko = _make_cluster_title_ko(
                    cluster.title, cluster.topic, cluster.country_code,
                )
        # junk 이벤트 제목 교체: 이벤트 제목이 junk이고 클러스터 제목이 정상이면 교체
        if _is_junk_title(event.title) and not _is_junk_title(cluster.title):
            event.title = cluster.title
            logger.debug("junk 이벤트 제목 교체: %s → %s", event.id, cluster.title[:40])
        # sub_topic: 클러스터가 general이고 이벤트가 구체적이면 갱신
        ev_sub = getattr(event, "sub_topic", "general") or "general"
        if (getattr(cluster, "sub_topic", "general") or "general") == "general" and ev_sub != "general":
            cluster.sub_topic = ev_sub
        # image_url: 아직 없으면 이벤트 것으로 채우기
        if not cluster.image_url and event.image_url:
            cluster.image_url = event.image_url
        # geo: 아직 없으면 이벤트 것으로 채우기
        if cluster.lat is None and event.lat is not None:
            cluster.lat = event.lat
            cluster.lon = event.lon
            cluster.country_code = event.country_code
            cluster.geohash5 = event.geohash5
        # KScore 즉시 계산 (calculate_trending 의존 제거)
        age_hours = (now - cluster.last_event_at).total_seconds() / 3600 if cluster.last_event_at else 0.0
        cluster.kscore, _ = _calc_kscore(
            event_count=cluster.event_count,
            is_spike=False,
            confidence=cluster.confidence,
            severity=cluster.severity,
            independent_sources=cluster.independent_sources or 1,
            source_tiers=cluster.source_tiers or [],
            age_hours=age_hours,
        )
        cluster.updated_at = now
    else:
        ai = generate_ai_title(
            [{"title": event.title, "body": event.body or ""}], event.topic, event.country_code,
        )
        if ai:
            ai_title_en, title_ko = ai
        else:
            ai_title_en = None
            title_ko = _make_cluster_title_ko(event.title, event.topic, event.country_code)
            # 쓰레기 제목일 때 영문도 폴백
            if _is_junk_title(event.title):
                ai_title_en, _ = _make_fallback_titles(event.topic, event.country_code)
        # KScore 즉시 계산
        initial_kscore, _ = _calc_kscore(
            event_count=1,
            is_spike=False,
            confidence=event.confidence,
            severity=event.severity,
            independent_sources=1,
            source_tiers=[event.source_tier] if event.source_tier else [],
        )
        cluster = IssueCluster(
            cluster_key=key,
            geohash5=geohash5,
            topic=event.topic,
            sub_topic=getattr(event, "sub_topic", "general") or "general",
            entity_anchor=event.entity_anchor,
            country_code=event.country_code,
            lat=event.lat,
            lon=event.lon,
            title=ai_title_en or event.title,
            title_ko=title_ko,
            event_count=1,
            severity=event.severity,
            confidence=event.confidence,
            kscore=initial_kscore,
            is_spike=False,
            source_tiers=[event.source_tier] if event.source_tier else [],
            independent_sources=1,
            first_event_at=event.event_time,
            last_event_at=event.event_time,
            window_start=window_cutoff,
            window_end=event.event_time + timedelta(minutes=WINDOW_MINUTES),
            image_url=event.image_url,
            is_verified=False,
        )
        db.add(cluster)
        await db.flush()

    db.add(ClusterEvent(cluster_id=cluster.id, event_id=event.id))

    # is_verified 양방향 자동 판별: confidence 하락 시 해제
    # confidence >= 0.70 AND "A" 티어 소스 포함
    # v5 (소스 확장): 모든 severity에서 independent_sources >= 2 필요
    # 단일 매체 보도로 verified 되면 안 됨
    tiers = cluster.source_tiers or []
    sources_ok = (cluster.independent_sources or 1) >= 2
    should_verify = cluster.confidence >= 0.70 and "A" in tiers and sources_ok

    just_verified = False
    if should_verify and not cluster.is_verified:
        cluster.is_verified = True
        just_verified = True
        logger.info(
            "클러스터 자동 검증됨: %s (confidence=%.2f, tiers=%s, sources=%d)",
            cluster.id, cluster.confidence, tiers,
            cluster.independent_sources or 1,
        )
    elif not should_verify and cluster.is_verified:
        cluster.is_verified = False
        logger.info(
            "클러스터 검증 해제됨: %s (confidence=%.2f, tiers=%s, sources=%d)",
            cluster.id, cluster.confidence, tiers,
            cluster.independent_sources or 1,
        )

    return cluster, just_verified


# ── Post-hoc 클러스터 병합 (소규모 → 대규모) ──────────────────────────────────

async def merge_fragmented_clusters(
    db: AsyncSession,
    *,
    dry_run: bool = False,
    max_merges: int = 200,
) -> list[tuple[str, str]]:
    """
    소규모 클러스터(event_count <= 2)를 같은 country:topic의
    더 큰 클러스터에 병합하여 파편화 해소.

    주기적으로 호출 (예: trending_engine의 5분 배치).

    Returns: [(absorbed_cluster_id, target_cluster_id), ...]
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # 1) 소규모 활성 클러스터 조회 (event_count <= 2, 7일 이내)
    small_q = (
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,  # noqa: E712
            IssueCluster.event_count <= 2,
            IssueCluster.first_event_at >= cutoff,
            IssueCluster.country_code.isnot(None),
        )
        .order_by(IssueCluster.event_count.asc(), IssueCluster.first_event_at.desc())
        .limit(500)
    )
    small_result = await db.execute(small_q)
    small_clusters = list(small_result.scalars().all())

    if not small_clusters:
        return []

    merged: list[tuple[str, str]] = []

    for small in small_clusters:
        if len(merged) >= max_merges:
            break

        # 2) 같은 country_code + topic의 더 큰 활성 클러스터 찾기
        target_q = (
            select(IssueCluster)
            .where(
                IssueCluster.is_active == True,  # noqa: E712
                IssueCluster.country_code == small.country_code,
                IssueCluster.topic == small.topic,
                IssueCluster.event_count > 2,
                IssueCluster.id != small.id,
                # 5일 이내 시간 근접성
                IssueCluster.first_event_at >= small.first_event_at - timedelta(days=5),
                IssueCluster.last_event_at <= small.last_event_at + timedelta(days=5),
            )
            .order_by(IssueCluster.event_count.desc())
            .limit(5)
        )
        target_result = await db.execute(target_q)
        targets = list(target_result.scalars().all())

        best_target = None
        best_sim = -1.0

        for target in targets:
            sim = _title_similarity(
                small.title, target.title,
                ko_a=small.title_ko, ko_b=target.title_ko,
            )
            # 병합용 완화된 임계값 (0.10) — AI 호출 제거 (DB 트랜잭션 내 외부 API 호출 금지)
            if sim >= 0.10 and sim > best_sim:
                best_sim = sim
                best_target = target

        if best_target is None:
            continue

        if dry_run:
            merged.append((str(small.id), str(best_target.id)))
            logger.info(
                "[DRY-RUN] 병합 후보: %s (events=%d) → %s (events=%d), sim=%.3f",
                small.title[:40], small.event_count,
                best_target.title[:40], best_target.event_count, best_sim,
            )
            continue

        # 3) ClusterEvent 레코드 이동
        await db.execute(
            update(ClusterEvent)
            .where(ClusterEvent.cluster_id == small.id)
            .values(cluster_id=best_target.id)
        )

        # 4) 타겟 클러스터 업데이트
        total_events = best_target.event_count + small.event_count
        best_target.event_count = total_events
        best_target.severity = max(best_target.severity, small.severity)
        if small.last_event_at and (not best_target.last_event_at or small.last_event_at > best_target.last_event_at):
            best_target.last_event_at = small.last_event_at
            best_target.window_end = small.last_event_at + timedelta(minutes=WINDOW_MINUTES)
        if small.first_event_at and (not best_target.first_event_at or small.first_event_at < best_target.first_event_at):
            best_target.first_event_at = small.first_event_at
        # confidence 가중 평균
        best_target.confidence = round(
            (best_target.confidence * (total_events - small.event_count)
             + small.confidence * small.event_count) / total_events, 3
        )
        # source_tiers 합치기
        existing_tiers = list(best_target.source_tiers or [])
        existing_tiers.extend(small.source_tiers or [])
        best_target.source_tiers = existing_tiers
        # KScore 재계산
        age_hours = (now - best_target.last_event_at).total_seconds() / 3600 if best_target.last_event_at else 0.0
        best_target.kscore, _ = _calc_kscore(
            event_count=best_target.event_count,
            is_spike=best_target.is_spike or False,
            confidence=best_target.confidence,
            severity=best_target.severity,
            independent_sources=best_target.independent_sources or 1,
            source_tiers=best_target.source_tiers or [],
            age_hours=age_hours,
        )
        best_target.updated_at = now

        # 5) 소규모 클러스터 비활성화
        small.is_active = False
        small.updated_at = now

        merged.append((str(small.id), str(best_target.id)))
        logger.info(
            "클러스터 병합: %s (events=%d) → %s (events=%d), sim=%.3f",
            small.title[:40], small.event_count,
            best_target.title[:40], best_target.event_count, best_sim,
        )

    if merged and not dry_run:
        await db.flush()
        logger.info("총 %d개 클러스터 병합 완료", len(merged))

    return merged


# ── 대형 클러스터 자동 분할 ──────────────────────────────────────────────────

SPLIT_MIN_EVENTS = 15  # 분할 대상 최소 이벤트 수


async def split_oversized_clusters(
    db: AsyncSession,
    *,
    min_events: int = SPLIT_MIN_EVENTS,
) -> list[tuple[str, str]]:
    """
    대형 클러스터를 sub_topic 기반으로 분할.

    - event_count >= min_events인 활성 클러스터 조회
    - 클러스터 내 이벤트들의 sub_topic 분포 확인
    - distinct non-general sub_topic 2개 이상이면 분리
    - 가장 큰 그룹은 원본 유지, 나머지 새 클러스터 생성

    Returns: [(original_cluster_id, new_cluster_id), ...]
    """
    from collections import Counter

    now = datetime.now(timezone.utc)

    # 1) 대형 활성 클러스터 조회
    big_q = (
        select(IssueCluster)
        .where(
            IssueCluster.is_active == True,  # noqa: E712
            IssueCluster.event_count >= min_events,
        )
        .order_by(IssueCluster.event_count.desc())
        .limit(100)
    )
    big_result = await db.execute(big_q)
    big_clusters = list(big_result.scalars().all())

    if not big_clusters:
        return []

    splits: list[tuple[str, str]] = []

    for cluster in big_clusters:
        # 2) 클러스터 내 이벤트 + sub_topic 조회
        ev_q = (
            select(NormalizedEvent)
            .join(ClusterEvent, ClusterEvent.event_id == NormalizedEvent.id)
            .where(ClusterEvent.cluster_id == cluster.id)
        )
        ev_result = await db.execute(ev_q)
        events = list(ev_result.scalars().all())

        # sub_topic 분포 계산 (general 제외)
        sub_counter: Counter[str] = Counter()
        events_by_sub: dict[str, list[NormalizedEvent]] = {}
        for ev in events:
            sub = getattr(ev, "sub_topic", "general") or "general"
            sub_counter[sub] += 1
            events_by_sub.setdefault(sub, []).append(ev)

        # non-general sub_topic이 2개 이상이어야 분할
        non_general = {k: v for k, v in sub_counter.items() if k != "general"}
        if len(non_general) < 2:
            continue

        # 3) 가장 큰 그룹 결정 (general + 최다 non-general → 원본 유지)
        largest_sub = max(non_general, key=lambda k: non_general[k])
        keep_subs = {"general", largest_sub}

        # 분리할 이벤트 그룹
        split_groups: dict[str, list[NormalizedEvent]] = {
            k: v for k, v in events_by_sub.items() if k not in keep_subs
        }

        if not split_groups:
            continue

        # 4) 각 분리 그룹에 대해 새 클러스터 생성
        for sub, sub_events in split_groups.items():
            if not sub_events:
                continue

            # 대표 이벤트 (severity 최고)
            rep = max(sub_events, key=lambda e: e.severity)

            # 제목 생성
            ai = generate_ai_title(
                [{"title": rep.title, "body": rep.body or ""}],
                rep.topic, rep.country_code,
            )
            if ai:
                new_title, new_title_ko = ai
            else:
                new_title = rep.title
                new_title_ko = _make_cluster_title_ko(rep.title, rep.topic, rep.country_code)

            new_severity = max(e.severity for e in sub_events)
            new_confidence = sum(e.confidence for e in sub_events) / len(sub_events)
            first_at = min(e.event_time for e in sub_events)
            last_at = max(e.event_time for e in sub_events)
            tiers = [e.source_tier for e in sub_events if e.source_tier]

            age_hours = (now - last_at).total_seconds() / 3600
            kscore, _ = _calc_kscore(
                event_count=len(sub_events),
                is_spike=False,
                confidence=round(new_confidence, 3),
                severity=new_severity,
                independent_sources=1,
                source_tiers=tiers,
                age_hours=age_hours,
            )

            new_cluster = IssueCluster(
                cluster_key=cluster.cluster_key,
                geohash5=cluster.geohash5,
                topic=cluster.topic,
                sub_topic=sub,
                entity_anchor=rep.entity_anchor,
                country_code=cluster.country_code,
                lat=cluster.lat,
                lon=cluster.lon,
                title=new_title,
                title_ko=new_title_ko,
                event_count=len(sub_events),
                severity=new_severity,
                confidence=round(new_confidence, 3),
                kscore=kscore,
                is_spike=False,
                source_tiers=tiers,
                independent_sources=1,
                first_event_at=first_at,
                last_event_at=last_at,
                window_start=first_at - timedelta(minutes=WINDOW_MINUTES),
                window_end=last_at + timedelta(minutes=WINDOW_MINUTES),
                image_url=rep.image_url,
                is_verified=False,
            )
            db.add(new_cluster)
            await db.flush()

            # ClusterEvent 이동
            for ev in sub_events:
                await db.execute(
                    update(ClusterEvent)
                    .where(
                        ClusterEvent.cluster_id == cluster.id,
                        ClusterEvent.event_id == ev.id,
                    )
                    .values(cluster_id=new_cluster.id)
                )

            splits.append((str(cluster.id), str(new_cluster.id)))
            logger.info(
                "클러스터 분할: %s [%s] → new %s (%d events, sub=%s)",
                cluster.title[:40], cluster.id,
                new_cluster.id, len(sub_events), sub,
            )

        # 5) 원본 클러스터 event_count 갱신
        remaining = len(events) - sum(len(v) for v in split_groups.values())
        cluster.event_count = remaining
        cluster.sub_topic = largest_sub
        # severity 재계산
        keep_events = events_by_sub.get("general", []) + events_by_sub.get(largest_sub, [])
        if keep_events:
            cluster.severity = max(e.severity for e in keep_events)
        cluster.updated_at = now

    if splits:
        await db.flush()
        logger.info("총 %d개 클러스터 분할 완료", len(splits))

    return splits
