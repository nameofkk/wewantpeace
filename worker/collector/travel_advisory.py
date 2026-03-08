"""
US State Department Travel Advisory 수집기.
6시간 주기로 미국 국무부 여행경보 데이터를 수집.

cadataapi.state.gov JSON API를 사용하여 Level 2+ 경보만 저장.
구조화된 country/level 데이터를 제공하므로
GPT 호출 없이 topic/severity/geo 매핑 가능 → 비용 절감.

TODO: 한국 외교부(0404.go.kr) 여행경보 수집 추가
  - https://www.0404.go.kr/dev/newest_list.mofa
  - RSS 피드 또는 스크래핑 필요 (구조 확인 후 구현)
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.raw_event import RawEvent

logger = logging.getLogger(__name__)

# US State Dept Travel Advisory JSON API
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
            # Updated 날짜가 바뀌면 새 이벤트로 인식 (경보 내용 변경)
            updated = advisory.get("Updated", "")
            # 날짜만 추출 (시간 부분 제외)하여 하루 단위로 중복 방지
            updated_date = updated[:10] if updated else ""
            external_id = f"us-travel-advisory:{country_code or country_name}:{level}:{updated_date}"

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
                "Travel Advisory 수집 완료: collected=%d, skipped=%d, errors=%s",
                result.collected,
                result.skipped,
                result.errors,
            )
            results.append(result)
        except Exception as e:
            logger.error("Travel Advisory 수집 오류: %s", e)
            results.append(TravelAdvisoryCollectResult(errors=[str(e)]))

        return results
