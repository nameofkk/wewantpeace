"""
EventClusterer: 60분 윈도우 기반 이슈 클러스터링.

클러스터 키: {geohash5}:{topic}
60분 윈도우 내 같은 키 → 같은 IssueCluster에 묶음.
"""
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

# 제목 단어 최소 겹침 비율 — 이 미만이면 같은 키라도 새 클러스터 생성
# (미국 폭풍 + 미국 총기 사건이 같은 US:disaster 버킷에 혼입되는 문제 방지)
MIN_TITLE_OVERLAP = 0.30


def _title_overlap(title_a: str, title_b: str) -> float:
    """두 제목의 단어 집합 교집합 비율 (Jaccard 유사도)."""
    _stop = {"the", "a", "an", "in", "on", "at", "to", "of", "and", "or",
             "is", "are", "was", "were", "has", "have", "had", "for", "with",
             "that", "this", "it", "its", "by", "be", "as", "not", "but"}
    def _words(t: str) -> set[str]:
        import re
        tokens = re.findall(r"[a-zA-Z가-힣]+", t.lower())
        return {w for w in tokens if w not in _stop and len(w) > 2}
    a, b = _words(title_a), _words(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

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
    import re
    stripped = re.sub(r'#\w+', '', title).strip()
    # 해시태그 제거 후 남은 글자가 5자 미만이면 쓰레기 제목
    return len(stripped) < 5


def _make_cluster_title_ko(
    title: str,
    topic: str,
    country_code: str | None,
) -> str | None:
    """
    클러스터 홈 카드용 한국어 제목 생성.
    UI에서 토픽·국기를 별도 표시하므로 번역된 핵심 제목만 반환.
    해시태그만 있는 저품질 제목은 None 반환 (프론트에서 영어 원문 폴백).
    """
    # 해시태그만 있는 쓰레기 제목 → 번역하지 않음
    if _is_junk_title(title):
        return None

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

    # 윈도우 내 기존 클러스터 조회 (window_end가 현재 이벤트 시각 이후면 아직 활성)
    result = await db.execute(
        select(IssueCluster).where(
            IssueCluster.cluster_key == key,
            IssueCluster.window_end >= event.event_time,
        ).order_by(IssueCluster.last_event_at.desc()).limit(1)
    )
    cluster = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    # ── 클러스터 혼입 방지 체크 ─────────────────────────────────────────────
    if cluster:
        no_country = not event.country_code
        no_geo = not event.geohash5

        # (1) 지오/국가 미분류 버킷이 MAX_EVENTS 초과 → 새 클러스터
        if no_country and no_geo and cluster.event_count >= MAX_EVENTS_UNKNOWN_GEO:
            cluster = None

        # (2) 제목 단어 겹침이 너무 낮으면 → 다른 이슈로 판단, 새 클러스터
        #     단, 고심각도 이벤트(양쪽 모두 >=50)는 같은 키(국가+토픽) 내에서
        #     영어/한국어 제목 간 겹침이 0%일 수 있으므로 검사 생략
        elif event.severity >= 50 and cluster.severity >= 50:
            pass  # 고심각도 속보 — 같은 국가+토픽이면 병합
        elif _title_overlap(event.title, cluster.title) < MIN_TITLE_OVERLAP:
            cluster = None

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
        # independent_sources: 이벤트마다 +1 (각 이벤트 = 독립 보도 1건)
        cluster.independent_sources = (cluster.independent_sources or 1) + 1
        # source_tiers: 새 tier 추가
        if event.source_tier:
            existing = list(cluster.source_tiers or [])
            existing.append(event.source_tier)
            cluster.source_tiers = existing
        # 제목 승격: 현재 제목이 쓰레기이고 새 이벤트 제목이 더 나으면 교체
        if _is_junk_title(cluster.title) and not _is_junk_title(event.title):
            ai = generate_ai_title(
                [{"title": event.title}, {"title": cluster.title}],
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
                [{"title": cluster.title}],
                cluster.topic, cluster.country_code,
            )
            if ai:
                cluster.title, cluster.title_ko = ai
            else:
                cluster.title_ko = _make_cluster_title_ko(
                    cluster.title, cluster.topic, cluster.country_code,
                )
        # geo: 아직 없으면 이벤트 것으로 채우기
        if cluster.lat is None and event.lat is not None:
            cluster.lat = event.lat
            cluster.lon = event.lon
            cluster.country_code = event.country_code
            cluster.geohash5 = event.geohash5
        # KScore 즉시 계산 (calculate_trending 의존 제거)
        cluster.kscore = _calc_kscore(
            event_count=cluster.event_count,
            is_spike=cluster.is_spike,
            confidence=cluster.confidence,
            severity=cluster.severity,
            independent_sources=cluster.independent_sources or 1,
            source_tiers=cluster.source_tiers or [],
        )
        cluster.updated_at = now
    else:
        ai = generate_ai_title(
            [{"title": event.title}], event.topic, event.country_code,
        )
        if ai:
            ai_title_en, title_ko = ai
        else:
            ai_title_en = None
            title_ko = _make_cluster_title_ko(event.title, event.topic, event.country_code)
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
