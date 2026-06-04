"""
기존 normalized_events의 event_time을 실제 발행 시간으로 소급 수정.

전략:
1. raw_metadata["published"] — ISO 8601 문자열 (시간 포함)만 사용
2. URL 날짜 추출 사용 안 함: 날짜만 알고 시간이 없어 자정(00:00 UTC)으로 설정되면
   KST로 09:00처럼 표시되어 실제 수집 시간과 달라 혼란을 줌

※ 정확한 시간 정보가 없으면 collected_at(실제 수집 시간)이 더 정확함
"""
import asyncio
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal

# 영어 월 이름 매핑
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# URL 날짜 패턴: /2026/02/17/ or /2026/2/17/
_URL_DATE_NUMERIC = re.compile(r'/(\d{4})/(\d{1,2})/(\d{1,2})/')
# URL 날짜 패턴: /2026/feb/22/ (Guardian 스타일)
_URL_DATE_ALPHA = re.compile(r'/(\d{4})/([a-z]{3})/(\d{1,2})/')


def parse_from_metadata(raw_metadata: dict) -> datetime | None:
    """raw_metadata["published"] 파싱."""
    pub_str = raw_metadata.get("published")
    if not pub_str:
        return None
    try:
        dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def parse_from_url(link: str) -> datetime | None:
    """URL 경로에서 날짜 추출."""
    if not link:
        return None

    # /2026/02/17/ 숫자형
    m = _URL_DATE_NUMERIC.search(link)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            pass

    # /2026/feb/22/ 알파형
    m = _URL_DATE_ALPHA.search(link)
    if m:
        month = _MONTH_MAP.get(m.group(2).lower())
        if month:
            try:
                return datetime(int(m.group(1)), month, int(m.group(3)),
                                tzinfo=timezone.utc)
            except ValueError:
                pass

    return None


async def fix_event_times():
    updated = 0
    skipped = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT
                ne.id          AS ne_id,
                re.source_type AS source_type,
                re.collected_at AS collected_at,
                re.raw_metadata AS raw_metadata
            FROM normalized_events ne
            JOIN raw_events re ON re.id = ne.raw_event_id
            WHERE re.raw_metadata IS NOT NULL
            ORDER BY ne.id
        """))
        rows = result.fetchall()

    print(f"대상 레코드: {len(rows)}개")

    async with AsyncSessionLocal() as db:
        for row in rows:
            ne_id = row.ne_id
            raw_metadata = row.raw_metadata or {}
            collected_at = row.collected_at
            if collected_at.tzinfo is None:
                collected_at = collected_at.replace(tzinfo=timezone.utc)

            try:
                # raw_metadata["published"] (시간 포함 ISO 8601)만 사용
                published_at = parse_from_metadata(raw_metadata)
                if published_at is None:
                    skipped += 1
                    continue

                # 미래 날짜(잘못된 데이터) 스킵
                if published_at > collected_at:
                    skipped += 1
                    continue

                await db.execute(
                    text("UPDATE normalized_events SET event_time = :t WHERE id = :id"),
                    {"t": published_at, "id": ne_id}
                )
                updated += 1

                if updated % 50 == 0:
                    await db.commit()
                    print(f"  {updated}개 업데이트 완료...")

            except Exception as e:
                errors += 1
                print(f"  오류 (ne_id={ne_id}): {e}")

        await db.commit()

    print("\n=== 소급 수정 완료 ===")
    print(f"  메타데이터(published) 기준 업데이트: {updated}개")
    print(f"  시간 정보 없어 스킵(collected_at 유지): {skipped}개")
    print(f"  오류: {errors}개")


if __name__ == "__main__":
    asyncio.run(fix_event_times())
