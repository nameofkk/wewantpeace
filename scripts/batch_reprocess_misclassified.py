"""
오분류 이벤트 배치 재처리 스크립트
- OpenAI 장애 기간 동안 keyword fallback으로 잘못 분류된 이벤트 정리
- 소규모 배치(30건)로 나눠서 Supabase statement_timeout 회피
"""
import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres",
)
BATCH_SIZE = 30


async def main():
    engine = create_async_engine(DB_URL, echo=False, pool_size=2)

    # ── 1. 대상 이벤트 수집 ──
    async with engine.begin() as conn:
        # a) topic='unknown'
        r = await conn.execute(text(
            "SELECT id, raw_event_id FROM normalized_events WHERE topic = 'unknown'"
        ))
        unknown_rows = r.fetchall()

        # b) severity >= 90 AND source_tier in B,C (최근 48시간)
        r = await conn.execute(text("""
            SELECT id, raw_event_id FROM normalized_events
            WHERE severity >= 90
            AND source_tier IN ('B', 'C')
            AND created_at > now() - interval '48 hours'
        """))
        high_sev_rows = r.fetchall()

    # 합치고 중복 제거
    all_ids = {}
    for row in unknown_rows + high_sev_rows:
        ne_id, raw_id = str(row[0]), str(row[1]) if row[1] else None
        all_ids[ne_id] = raw_id

    total = len(all_ids)
    print(f"재처리 대상: {total}건 (unknown={len(unknown_rows)}, high_sev_low_tier={len(high_sev_rows)})")

    if total == 0:
        print("처리할 이벤트 없음")
        await engine.dispose()
        return

    ne_ids = list(all_ids.keys())
    raw_ids = [v for v in all_ids.values() if v]

    # ── 2. 배치별 삭제 ──
    deleted_ce = 0
    deleted_ne = 0
    reset_raw = 0

    for i in range(0, len(ne_ids), BATCH_SIZE):
        batch = ne_ids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"\n--- 배치 {batch_num} ({len(batch)}건) ---")

        async with engine.begin() as conn:
            # a) cluster_events 삭제
            r = await conn.execute(text(
                "DELETE FROM cluster_events WHERE event_id = ANY(:ids)"
            ), {"ids": batch})
            deleted_ce += r.rowcount
            print(f"  cluster_events 삭제: {r.rowcount}")

            # b) normalized_events 삭제
            r = await conn.execute(text(
                "DELETE FROM normalized_events WHERE id = ANY(:ids)"
            ), {"ids": batch})
            deleted_ne += r.rowcount
            print(f"  normalized_events 삭제: {r.rowcount}")

        print(f"  ✓ 배치 {batch_num} 커밋 완료")

    # ── 3. raw_events 재처리 플래그 (배치) ──
    print(f"\n--- raw_events processed=false 리셋 ---")
    for i in range(0, len(raw_ids), BATCH_SIZE):
        batch = raw_ids[i : i + BATCH_SIZE]
        async with engine.begin() as conn:
            r = await conn.execute(text(
                "UPDATE raw_events SET processed = false WHERE id = ANY(:ids) AND processed = true"
            ), {"ids": batch})
            reset_raw += r.rowcount

    print(f"  raw_events 리셋: {reset_raw}건")

    # ── 4. 빈 클러스터 정리 ──
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            DELETE FROM issue_clusters
            WHERE id IN (
                SELECT ic.id FROM issue_clusters ic
                LEFT JOIN cluster_events ce ON ce.cluster_id = ic.id
                WHERE ce.id IS NULL
            )
        """))
        print(f"\n빈 클러스터 삭제: {r.rowcount}건")

    # ── 요약 ──
    print(f"""
╔══════════════════════════════════╗
║       재처리 완료 요약            ║
╠══════════════════════════════════╣
║  cluster_events 삭제: {deleted_ce:>6}건   ║
║  normalized_events 삭제: {deleted_ne:>4}건   ║
║  raw_events 리셋:       {reset_raw:>4}건   ║
╚══════════════════════════════════╝
→ Worker가 자동으로 리셋된 raw_events를 재처리합니다.
""")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
