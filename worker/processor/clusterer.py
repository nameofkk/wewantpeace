"""
EventClusterer: 60분 윈도우 기반 이슈 클러스터링.

클러스터 키: {country_code}:{topic} 또는 {geohash4}:{topic}
60분 윈도우 내 같은 키 + 제목 유사도 검사 → 서브토픽별 분리.
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
from worker.processor.trending_engine import _calc_kscore
from worker.processor.ai_title import generate_ai_title

logger = logging.getLogger(__name__)

WINDOW_MINUTES = 60

# geohash 없는 버킷("0000:topic")의 최대 이벤트 수 — 초과 시 새 클러스터 생성
MAX_EVENTS_UNKNOWN_GEO = 2

# 제목 유사도 임계값
MIN_TITLE_OVERLAP = 0.25           # 일반 이벤트
MIN_TITLE_OVERLAP_HIGH_SEV = 0.10  # 고심각도 (severity >= 50 양쪽)

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


def _title_similarity(
    en_a: str, en_b: str,
    ko_a: str | None = None, ko_b: str | None = None,
) -> float:
    """
    두 제목의 유사도 (0.0 ~ 1.0).
    영어(스테밍 Jaccard)와 한국어(Jaccard)를 각각 계산 후 max 반환.
    언어가 다른 제목 간 교차 비교 문제를 해결.
    """
    # 영어 스테밍 Jaccard
    a_en = _stemmed_en_words(en_a)
    b_en = _stemmed_en_words(en_b)
    en_sim = (len(a_en & b_en) / len(a_en | b_en)) if (a_en and b_en) else 0.0

    # 한국어 Jaccard
    ko_sim = 0.0
    if ko_a and ko_b:
        a_ko = _ko_words(ko_a)
        b_ko = _ko_words(ko_b)
        if a_ko and b_ko:
            ko_sim = len(a_ko & b_ko) / len(a_ko | b_ko)

    return max(en_sim, ko_sim)

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
) -> tuple[IssueCluster | None, bool]:
    """
    NormalizedEvent를 60분 윈도우 내 같은 cluster_key의 IssueCluster에 할당.
    없으면 새 클러스터 생성.

    Returns:
        (IssueCluster | None, just_verified: bool)
        just_verified=True: 이번 업데이트로 is_verified가 False→True로 전환됨.

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

    for cand in candidates:
        no_country = not event.country_code
        no_geo = not event.geohash5

        # (1) 지오/국가 미분류 버킷이 MAX_EVENTS 초과 → 이 후보 건너뛰기
        if no_country and no_geo and cand.event_count >= MAX_EVENTS_UNKNOWN_GEO:
            continue

        # (2) 제목 유사도 계산 (스테밍 + 이중 언어)
        sim = _title_similarity(
            event.title, cand.title,
            ko_a=getattr(event, "title_ko", None),
            ko_b=cand.title_ko,
        )

        # 고심각도(양쪽 모두 >=50)는 낮은 임계값, 일반은 높은 임계값
        threshold = MIN_TITLE_OVERLAP_HIGH_SEV \
            if event.severity >= 50 and cand.severity >= 50 \
            else MIN_TITLE_OVERLAP

        if sim >= threshold and sim > best_sim:
            best_sim = sim
            cluster = cand

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
        cluster.kscore = _calc_kscore(
            event_count=cluster.event_count,
            is_spike=cluster.is_spike,
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
        initial_kscore = _calc_kscore(
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
    # severity ≥ 75인 경우 independent_sources ≥ 2도 필요 (고위험 이벤트 검증 강화)
    tiers = cluster.source_tiers or []
    sources_ok = True
    if cluster.severity >= 75:
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
