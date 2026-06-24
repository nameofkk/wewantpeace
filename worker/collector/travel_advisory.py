"""
Travel Advisory 수집기 (US / Korea / UK).
6시간 주기로 여행경보 데이터를 수집.

1. US State Department  - cadataapi.state.gov JSON API (Level 2+)
2. Korean MOFA          - 공공데이터포털 getTravelAlarmList2 (황색경보 이상)
3. UK FCDO              - GOV.UK Content API (top-20 고위험 국가)

구조화된 country/level 데이터를 제공하므로
GPT 호출 없이 topic/severity/geo 매핑 가능 → 비용 절감.
"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# US State Dept
# ──────────────────────────────────────────────
US_ADVISORY_API_URL = "https://cadataapi.state.gov/api/TravelAdvisories"

# Advisory Level → severity 매핑 (Level 1은 수집 안 함)
_LEVEL_SEVERITY: dict[int, int] = {
    2: 30,   # Exercise Increased Caution
    3: 55,   # Reconsider Travel
    4: 80,   # Do Not Travel
}

# Level 1은 노이즈이므로 수집 제외 (최소 Level 2부터)
MIN_ADVISORY_LEVEL = 2

# Title에서 Level 추출: "Country Name - Level X: Description"
_LEVEL_RE = re.compile(r"Level\s+(\d)", re.IGNORECASE)

# Title에서 국가명 추출: "Country Name - Level X: ..."
_COUNTRY_RE = re.compile(r"^(.+?)\s*[-–—]\s*Level\s+\d", re.IGNORECASE)

# ISO 3166-1 alpha-2 → 대표 위경도 (수도 좌표 기준, 주요 국가만)
# 전체 매핑은 normalizer의 COUNTRY_MAP에 의존하므로 여기서는 최소한만 정의
# structured_country를 제공하면 tasks.py에서 COUNTRY_MAP으로 geo 매핑함

# ──────────────────────────────────────────────
# Korean MOFA (외교부 여행경보)
# ──────────────────────────────────────────────
KR_ADVISORY_API_URL = (
    "http://apis.data.go.kr/1262000/TravelAlarmService2/getTravelAlarmList2"
)

# 한국 외교부 경보 수준 → severity 매핑
# 남색경보(1) = 여행유의 → skip (Level 1 동급)
# 황색경보(2) = 여행자제 → severity 30
# 적색경보(3) = 출국권고 → severity 55
# 흑색경보(4) = 여행금지 → severity 80
_KR_LEVEL_SEVERITY: dict[int, int] = {
    2: 30,
    3: 55,
    4: 80,
}

_KR_LEVEL_DESC: dict[int, str] = {
    1: "여행유의 (남색경보)",
    2: "여행자제 (황색경보)",
    3: "출국권고 (적색경보)",
    4: "여행금지 (흑색경보)",
}

# ──────────────────────────────────────────────
# UK FCDO
# ──────────────────────────────────────────────
UK_CONTENT_API_BASE = "https://www.gov.uk/api/content/foreign-travel-advice"

# Top-20 고위험 국가 (slug, ISO alpha-2 코드, 표시용 영문명)
_UK_PRIORITY_COUNTRIES: list[tuple[str, str, str]] = [
    ("afghanistan", "AF", "Afghanistan"),
    ("iraq", "IQ", "Iraq"),
    ("syria", "SY", "Syria"),
    ("yemen", "YE", "Yemen"),
    ("somalia", "SO", "Somalia"),
    ("libya", "LY", "Libya"),
    ("south-sudan", "SS", "South Sudan"),
    ("north-korea", "KP", "North Korea"),
    ("ukraine", "UA", "Ukraine"),
    ("sudan", "SD", "Sudan"),
    ("mali", "ML", "Mali"),
    ("central-african-republic", "CF", "Central African Republic"),
    ("democratic-republic-of-the-congo", "CD", "DR Congo"),
    ("iran", "IR", "Iran"),
    ("pakistan", "PK", "Pakistan"),
    ("haiti", "HT", "Haiti"),
    ("burkina-faso", "BF", "Burkina Faso"),
    ("niger", "NE", "Niger"),
    ("myanmar", "MM", "Myanmar"),
    ("lebanon", "LB", "Lebanon"),
]

# FCDO 경보 문구 → severity 매핑 (소문자 매칭)
# 주의: "all but essential" 이 "all travel"을 포함하므로 더 구체적인 것 먼저 매칭
_UK_SEVERITY_MAP: list[tuple[str, int]] = [
    ("advise against all but essential travel", 55),
    ("advise against all travel", 80),
]


@dataclass
class TravelAdvisoryCollectResult:
    display_name: str = "US Travel Advisory"
    collected: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    raw_event_ids: list = field(default_factory=list)


def _parse_level(title: str) -> int | None:
    """Title 문자열에서 Advisory Level (1-4) 추출."""
    match = _LEVEL_RE.search(title)
    if match:
        level = int(match.group(1))
        if 1 <= level <= 4:
            return level
    return None


def _parse_country_name(title: str) -> str:
    """Title 문자열에서 국가명 추출.

    형식: "Country Name - Level X: Description"
    """
    match = _COUNTRY_RE.match(title)
    if match:
        return match.group(1).strip()
    return ""


def _parse_country_code(category: list) -> str:
    """Category 배열에서 2글자 국가 코드 추출.

    API 응답 형식: ["SA"], ["IZ"] 등
    """
    if category and isinstance(category, list) and len(category) > 0:
        code = category[0]
        if isinstance(code, str) and len(code) == 2:
            return code.upper()
    return ""


def _strip_html(text: str) -> str:
    """HTML 태그 제거 후 텍스트만 추출."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class TravelAdvisoryCollector:
    """US State Department Travel Advisory 수집기."""

    TIMEOUT = 30  # seconds

    async def collect(
        self,
        db: AsyncSession,
        redis=None,
    ) -> TravelAdvisoryCollectResult:
        """미국 국무부 Travel Advisory API에서 Level 2+ 경보 수집."""
        result = TravelAdvisoryCollectResult()

        # API 호출
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                async with session.get(US_ADVISORY_API_URL) as resp:
                    if resp.status != 200:
                        result.errors.append(f"HTTP {resp.status}")
                        return result
                    data = await resp.json(content_type=None)
        except asyncio.TimeoutError:
            result.errors.append("API 타임아웃")
            return result
        except Exception as e:
            result.errors.append(f"API 오류: {e}")
            return result

        # API 응답이 리스트인지 확인
        if not isinstance(data, list):
            result.errors.append(f"예상치 못한 응답 형식: {type(data).__name__}")
            return result

        if not data:
            return result

        for advisory in data:
            title = advisory.get("Title", "")
            if not title:
                result.skipped += 1
                continue

            # Level 추출
            level = _parse_level(title)
            if level is None:
                result.skipped += 1
                continue

            # Level 1 (Exercise Normal Precautions) → 노이즈, 스킵
            if level < MIN_ADVISORY_LEVEL:
                result.skipped += 1
                continue

            # 국가 정보 추출
            country_name = _parse_country_name(title)
            country_code = _parse_country_code(advisory.get("Category", []))

            if not country_name:
                result.skipped += 1
                continue

            # external_id: 국가코드+레벨로 중복 방지
            # 같은 국가의 같은 레벨이면 중복으로 처리
            # 레벨이 변경되면 새 이벤트로 인식 (날짜 제거하여 같은 날 중복 방지)
            external_id = f"us-travel-advisory:{country_code or country_name}:{level}"

            # 중복 확인
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "api",
                    RawEvent.external_id == external_id,
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            # severity 매핑
            severity = _LEVEL_SEVERITY.get(level, 30)

            # 발행 시간 파싱
            published_at = None
            pub_str = advisory.get("Published") or advisory.get("Updated")
            if pub_str:
                try:
                    published_at = datetime.fromisoformat(
                        pub_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            collected_at = datetime.now(timezone.utc)

            # Summary에서 HTML 제거하여 본문 텍스트 추출
            summary_html = advisory.get("Summary", "")
            summary_text = _strip_html(summary_html)

            # raw_text: 제목 + 요약
            level_desc = {
                2: "Exercise Increased Caution",
                3: "Reconsider Travel",
                4: "Do Not Travel",
            }
            raw_text = (
                f"US Travel Advisory: {country_name} - Level {level}: "
                f"{level_desc.get(level, '')}. {summary_text}"
            )

            link = advisory.get("Link", "")

            raw_metadata = {
                "title": title[:512],
                "link": link,
                "advisory_level": level,
                "country_name": country_name,
                "country_code": country_code,
                "published": (
                    published_at.isoformat()
                    if published_at
                    else collected_at.isoformat()
                ),
                "time_source": (
                    "advisory_published" if published_at else "collected_at"
                ),
                # 구조화 데이터 (normalizer에서 GPT 스킵용)
                "structured_topic": "diplomacy",
                "structured_severity": severity,
                "structured_country": country_name,
                # 위경도는 없음 → tasks.py에서 COUNTRY_MAP으로 매핑
            }

            raw_event = RawEvent(
                source_channel_id=None,  # SourceChannel 불요 (고정 API)
                source_type="api",
                external_id=external_id,
                raw_text=raw_text[:10000],
                raw_metadata=raw_metadata,
                lang="en",
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(
        self, db: AsyncSession, redis=None
    ) -> list[TravelAdvisoryCollectResult]:
        """Travel Advisory 데이터 수집 (단일 API).

        다른 수집기와 인터페이스 통일을 위해 collect_all → list[Result] 형태.
        """
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "US Travel Advisory 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected,
                result.skipped,
                result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("US Travel Advisory 수집 오류: %s", e)
            results.append(TravelAdvisoryCollectResult(errors=[str(e)]))

        return results


# ═══════════════════════════════════════════════
# Korean MOFA Travel Advisory Collector
# ═══════════════════════════════════════════════


class KoreaTravelAdvisoryCollector:
    """한국 외교부 여행경보 수집기 (공공데이터포털 API)."""

    TIMEOUT = 30  # seconds

    async def collect(
        self,
        db: AsyncSession,
        redis=None,
    ) -> TravelAdvisoryCollectResult:
        """공공데이터포털 getTravelAlarmList2 API에서 황색경보(2) 이상 수집."""
        result = TravelAdvisoryCollectResult(display_name="Korea Travel Advisory")

        # API 키 확인
        api_key = os.environ.get("KOREA_DATA_API_KEY", "")
        if not api_key:
            logger.warning(
                "KOREA_DATA_API_KEY 환경변수 미설정 → 한국 외교부 여행경보 수집 건너뜀"
            )
            result.errors.append("KOREA_DATA_API_KEY not set")
            return result

        params = {
            "serviceKey": api_key,
            "returnType": "JSON",
            "numOfRows": "200",
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as session:
                async with session.get(
                    KR_ADVISORY_API_URL, params=params
                ) as resp:
                    if resp.status != 200:
                        result.errors.append(f"HTTP {resp.status}")
                        return result
                    data = await resp.json(content_type=None)
        except asyncio.TimeoutError:
            result.errors.append("API 타임아웃")
            return result
        except Exception as e:
            result.errors.append(f"API 오류: {e}")
            return result

        # 응답 구조: { "response": { "body": { "items": [...] } } }
        try:
            items = data["response"]["body"]["items"]
        except (KeyError, TypeError):
            result.errors.append(
                f"예상치 못한 응답 구조: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )
            return result

        if not items:
            return result

        # items가 단일 객체일 수 있음 (1건일 때)
        if isinstance(items, dict):
            items = [items]

        for item in items:
            alarm_lvl_raw = item.get("alarmLvl")
            if alarm_lvl_raw is None:
                result.skipped += 1
                continue

            try:
                alarm_lvl = int(alarm_lvl_raw)
            except (ValueError, TypeError):
                result.skipped += 1
                continue

            # 남색경보(1) → skip (US Level 1과 동급)
            if alarm_lvl < 2:
                result.skipped += 1
                continue

            country_en = item.get("countryEnName", "").strip()
            country_ko = item.get("countryName", "").strip()
            country_code = (item.get("countryIsoAlp2") or "").strip().upper()
            written_dt = item.get("writtenDt", "")

            if not country_en and not country_ko:
                result.skipped += 1
                continue

            country_name = country_en or country_ko

            # external_id: 국가코드+레벨로 중복 방지 (날짜 제거)
            external_id = (
                f"kr-travel-advisory:"
                f"{country_code or country_name}:{alarm_lvl}"
            )

            # 중복 확인
            existing = await db.execute(
                select(RawEvent).where(
                    RawEvent.source_type == "api",
                    RawEvent.external_id == external_id,
                )
            )
            if existing.scalar_one_or_none():
                result.skipped += 1
                continue

            severity = _KR_LEVEL_SEVERITY.get(alarm_lvl, 30)

            # 발행 시간 파싱
            published_at = None
            if written_dt:
                try:
                    published_at = datetime.fromisoformat(
                        written_dt.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    # YYYYMMDD 형식일 수 있음
                    try:
                        published_at = datetime.strptime(
                            written_dt[:8], "%Y%m%d"
                        ).replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

            collected_at = datetime.now(timezone.utc)

            level_desc = _KR_LEVEL_DESC.get(alarm_lvl, f"Level {alarm_lvl}")
            raw_text = (
                f"Korea Travel Advisory: {country_name} - {level_desc}. "
                f"한국 외교부 여행경보 {alarm_lvl}단계 발령."
            )

            raw_metadata = {
                "title": f"한국 외교부 여행경보: {country_name} - {level_desc}"[:512],
                "link": "https://www.0404.go.kr",
                "advisory_level": alarm_lvl,
                "country_name": country_name,
                "country_name_ko": country_ko,
                "country_code": country_code,
                "published": (
                    published_at.isoformat()
                    if published_at
                    else collected_at.isoformat()
                ),
                "time_source": (
                    "advisory_published" if published_at else "collected_at"
                ),
                "structured_topic": "diplomacy",
                "structured_severity": severity,
                "structured_country": country_name,
                "source_agency": "korea_mofa",
            }

            raw_event = RawEvent(
                source_channel_id=None,
                source_type="api",
                external_id=external_id,
                raw_text=raw_text[:10000],
                raw_metadata=raw_metadata,
                lang="ko",
                collected_at=collected_at,
            )
            db.add(raw_event)
            result.raw_event_ids.append(raw_event)
            result.collected += 1

        return result

    async def collect_all(
        self, db: AsyncSession, redis=None
    ) -> list[TravelAdvisoryCollectResult]:
        """한국 외교부 여행경보 수집."""
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "Korea Travel Advisory 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected,
                result.skipped,
                result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("Korea Travel Advisory 수집 오류: %s", e)
            results.append(
                TravelAdvisoryCollectResult(
                    display_name="Korea Travel Advisory", errors=[str(e)]
                )
            )
        return results


# ═══════════════════════════════════════════════
# UK FCDO Travel Advisory Collector
# ═══════════════════════════════════════════════


class UKTravelAdvisoryCollector:
    """UK FCDO 여행경보 수집기 (GOV.UK Content API)."""

    TIMEOUT = 30  # seconds per request

    @staticmethod
    def _to_str(v) -> str:
        """GOV.UK API가 string 대신 list를 반환하는 경우 안전 변환."""
        if isinstance(v, list):
            return " ".join(str(x) for x in v)
        return str(v) if v else ""

    @staticmethod
    def _parse_fcdo_severity(document: dict) -> int:
        """FCDO 문서에서 severity를 추출.

        document.details.alert_status 또는 본문에서 경보 수준 판별.
        """
        details = document.get("details", {})

        # GOV.UK API가 list를 반환할 수 있으므로 안전 변환
        _to_str = UKTravelAdvisoryCollector._to_str

        # 1) alert_status 필드 확인
        alert_status = _to_str(details.get("alert_status")).lower().strip()
        if alert_status:
            for phrase, sev in _UK_SEVERITY_MAP:
                if phrase in alert_status:
                    return sev

        # 2) summary 또는 body에서 텍스트 매칭
        summary = _to_str(details.get("summary")).lower()
        body = _to_str(details.get("body")).lower()
        combined = f"{summary} {body}"

        # 더 엄격한 것(all travel) 먼저 매칭
        for phrase, sev in _UK_SEVERITY_MAP:
            if phrase in combined:
                return sev

        # 기본 (advisory 존재하지만 위 카테고리에 해당 안 됨)
        return 30

    async def collect(
        self,
        db: AsyncSession,
        redis=None,
    ) -> TravelAdvisoryCollectResult:
        """UK FCDO Content API에서 top-20 고위험 국가 여행경보 수집."""
        result = TravelAdvisoryCollectResult(display_name="UK Travel Advisory")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
        ) as session:
            for slug, country_code, country_name in _UK_PRIORITY_COUNTRIES:
                url = f"{UK_CONTENT_API_BASE}/{slug}"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 404:
                            # 해당 국가 페이지 없음 → 무시
                            result.skipped += 1
                            continue
                        if resp.status != 200:
                            result.errors.append(
                                f"{slug}: HTTP {resp.status}"
                            )
                            continue
                        data = await resp.json(content_type=None)
                except asyncio.TimeoutError:
                    result.errors.append(f"{slug}: 타임아웃")
                    continue
                except Exception as e:
                    result.errors.append(f"{slug}: {e}")
                    continue

                # updated_at 추출
                updated_at = data.get("updated_at") or data.get("public_updated_at") or ""

                # severity를 external_id에 포함 → 경보 수준 변경 시 새 이벤트로 인식
                severity = self._parse_fcdo_severity(data)
                external_id = f"uk-travel-advisory:{country_code}:{severity}"

                # 중복 확인
                existing = await db.execute(
                    select(RawEvent).where(
                        RawEvent.source_type == "api",
                        RawEvent.external_id == external_id,
                    )
                )
                if existing.scalar_one_or_none():
                    result.skipped += 1
                    continue

                # 발행 시간 파싱
                published_at = None
                if updated_at:
                    try:
                        published_at = datetime.fromisoformat(
                            updated_at.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                collected_at = datetime.now(timezone.utc)

                # severity에 따른 경보 설명
                if severity >= 80:
                    level_desc = "Advise against all travel"
                elif severity >= 55:
                    level_desc = "Advise against all but essential travel"
                else:
                    level_desc = "Travel advisory in effect"

                # summary 텍스트 추출
                details = data.get("details", {})
                summary_text = _strip_html(details.get("summary") or "")

                raw_text = (
                    f"UK FCDO Travel Advisory: {country_name} - {level_desc}. "
                    f"{summary_text}"
                )

                raw_metadata = {
                    "title": f"UK FCDO: {country_name} - {level_desc}"[:512],
                    "link": f"https://www.gov.uk/foreign-travel-advice/{slug}",
                    "advisory_level": severity,  # FCDO는 이산 레벨 없음, severity 직접
                    "country_name": country_name,
                    "country_code": country_code,
                    "published": (
                        published_at.isoformat()
                        if published_at
                        else collected_at.isoformat()
                    ),
                    "time_source": (
                        "advisory_published" if published_at else "collected_at"
                    ),
                    "structured_topic": "diplomacy",
                    "structured_severity": severity,
                    "structured_country": country_name,
                    "source_agency": "uk_fcdo",
                }

                raw_event = RawEvent(
                    source_channel_id=None,
                    source_type="api",
                    external_id=external_id,
                    raw_text=raw_text[:10000],
                    raw_metadata=raw_metadata,
                    lang="en",
                    collected_at=collected_at,
                )
                db.add(raw_event)
                result.raw_event_ids.append(raw_event)
                result.collected += 1

        return result

    async def collect_all(
        self, db: AsyncSession, redis=None
    ) -> list[TravelAdvisoryCollectResult]:
        """UK FCDO 여행경보 수집."""
        results = []
        try:
            result = await self.collect(db, redis=redis)
            logger.info(
                "UK FCDO Travel Advisory 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected,
                result.skipped,
                result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("UK FCDO Travel Advisory 수집 오류: %s", e)
            results.append(
                TravelAdvisoryCollectResult(
                    display_name="UK Travel Advisory", errors=[str(e)]
                )
            )
        return results
