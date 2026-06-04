"""기존 UCDP normalized_events의 source_tier를 "A"로 수정.

UCDP 수집기가 raw_metadata["source_tier"]="A"로 저장했지만,
process_raw_event에서 source_channel_id=NULL이면 기본값 "C"로
NormalizedEvent에 저장한 버그를 수정.

사용법:
  DATABASE_URL="postgresql+asyncpg://..." python scripts/fix_ucdp_source_tier.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL 환경변수 필요")
        sys.exit(1)

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with async_session() as db:
        # 1. UCDP raw_events와 연결된 normalized_events 중 source_tier != "A"인 것 수정
        # raw_events.external_id가 'ucdp:'로 시작하는 이벤트 식별
        result = await db.execute(text("""
            UPDATE normalized_events ne
            SET source_tier = 'A'
            FROM raw_events re
            WHERE ne.raw_event_id = re.id
              AND re.external_id LIKE 'ucdp:%'
              AND ne.source_tier != 'A'
            RETURNING ne.id
        """))
        updated_ids = result.fetchall()
        count = len(updated_ids)

        if count > 0:
            await db.commit()
            print(f"[완료] {count}개 UCDP normalized_events의 source_tier를 'A'로 수정")
        else:
            print("[완료] 수정할 UCDP 이벤트 없음 (이미 모두 'A'이거나 UCDP 데이터 없음)")

        # 2. issue_clusters에도 source_tiers 배열에 "A" 반영 필요한지 확인
        cluster_result = await db.execute(text("""
            SELECT DISTINCT ic.id, ic.source_tiers
            FROM issue_clusters ic
            JOIN cluster_events ce ON ce.cluster_id = ic.id
            JOIN normalized_events ne ON ne.id = ce.event_id
            JOIN raw_events re ON re.id = ne.raw_event_id
            WHERE re.external_id LIKE 'ucdp:%'
              AND (ic.source_tiers IS NULL OR NOT ('A' = ANY(ic.source_tiers)))
        """))
        clusters = cluster_result.fetchall()
        cl_count = 0
        for cl in clusters:
            existing = list(cl.source_tiers or [])
            if "A" not in existing:
                existing.append("A")
            await db.execute(text("""
                UPDATE issue_clusters SET source_tiers = :tiers WHERE id = :id
            """), {"tiers": existing, "id": cl.id})
            cl_count += 1

        if cl_count > 0:
            await db.commit()
            print(f"[완료] {cl_count}개 issue_clusters에 source_tier 'A' 추가")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
