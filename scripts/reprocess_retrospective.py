"""
회고/후속 기사 재처리 스크립트
- severity >= 60인데 본문에 과거 시제 단서가 있는 이벤트 식별
- 해당 이벤트 삭제 → raw_events 리셋 → worker가 개선된 AI 프롬프트로 재분류
"""
import asyncio
import re
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
BATCH_SIZE = 30

# 과거 사건 단서 패턴
RETROSPECTIVE_PATTERNS = [
    r"january\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:crash|attack|incident|disaster)",
    r"february\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:crash|attack|incident|disaster)",
    r"(?:last|past)\s+(?:january|february|march|year|month)",
    r"(?:in|since|back in)\s+(?:20\d\d|19\d\d)",
    r"\b(?:months?|years?)\s+ago\b",
    r"\b(?:looking back|retrospective|revisit|anniversary)\b",
    r"\blast\s+(?:year|month|january|february|march|april|may|june|july|august|september|october|november|december)\b",
    r"\b(?:january|february) (?:20)?2[0-5]\b",  # Jan/Feb 2020-2025
    r"\bnew (?:footage|video|images?|evidence)\b.*(?:reveal|show|emerge)",
]


async def main():
    engine = create_async_engine(DB_URL, echo=False, pool_size=1, max_overflow=0,
                                  connect_args={"server_settings": {"statement_timeout": "30000"}})

    # 1. severity >= 60 이벤트 중 회고 기사 후보 찾기
    print("=== 회고 기사 후보 스캔 (severity >= 60, 최근 48시간) ===\n")

    async with engine.begin() as conn:
        r = await conn.execute(text("""
            SELECT ne.id, ne.raw_event_id, ne.title, ne.body, ne.severity, ne.topic,
                   ne.source_tier, ne.created_at
            FROM normalized_events ne
            WHERE ne.severity >= 60
            AND ne.created_at > now() - interval '48 hours'
            AND ne.is_duplicate = false
            ORDER BY ne.created_at DESC
        """))
        candidates = r.fetchall()

    print(f"스캔 대상: {len(candidates)}건 (severity >= 60, 48h)")

    # 2. 패턴 매칭으로 회고 기사 식별
    retro_ids = []
    retro_raw_ids = []

    for row in candidates:
        ne_id, raw_id, title, body, sev, topic, tier, created = row
        combined = f"{title or ''} {(body or '')[:1000]}".lower()

        for pattern in RETROSPECTIVE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                print(f"  ✓ [{topic}] sev={sev} tier={tier} | {(title or '')[:80]}")
                print(f"    매칭: {pattern}")
                retro_ids.append(str(ne_id))
                if raw_id:
                    retro_raw_ids.append(str(raw_id))
                break

    total = len(retro_ids)
    print(f"\n회고 기사 감지: {total}건")

    if total == 0:
        print("재처리할 이벤트 없음")
        await engine.dispose()
        return

    # 3. 배치 삭제
    deleted_ce = 0
    deleted_ne = 0
    reset_raw = 0

    for i in range(0, len(retro_ids), BATCH_SIZE):
        batch = retro_ids[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"\n--- 배치 {batch_num} ({len(batch)}건) ---")

        async with engine.begin() as conn:
            r = await conn.execute(text(
                "DELETE FROM cluster_events WHERE event_id = ANY(:ids)"
            ), {"ids": batch})
            deleted_ce += r.rowcount
            print(f"  cluster_events 삭제: {r.rowcount}")

            r = await conn.execute(text(
                "DELETE FROM normalized_events WHERE id = ANY(:ids)"
            ), {"ids": batch})
            deleted_ne += r.rowcount
            print(f"  normalized_events 삭제: {r.rowcount}")

        print(f"  ✓ 배치 {batch_num} 커밋 완료")

    # 4. raw_events 리셋
    print(f"\n--- raw_events processed=false 리셋 ---")
    for i in range(0, len(retro_raw_ids), BATCH_SIZE):
        batch = retro_raw_ids[i:i + BATCH_SIZE]
        async with engine.begin() as conn:
            r = await conn.execute(text(
                "UPDATE raw_events SET processed = false WHERE id = ANY(:ids) AND processed = true"
            ), {"ids": batch})
            reset_raw += r.rowcount

    print(f"  raw_events 리셋: {reset_raw}건")

    # 5. 빈 클러스터 정리
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            DELETE FROM issue_clusters
            WHERE id IN (
                SELECT ic.id FROM issue_clusters ic
                LEFT JOIN cluster_events ce ON ce.cluster_id = ic.id
                WHERE ce.event_id IS NULL
            )
        """))
        print(f"\n빈 클러스터 삭제: {r.rowcount}건")

    print(f"""
╔═══════════════════════════════════╗
║      회고 기사 재처리 완료         ║
╠═══════════════════════════════════╣
║  회고 기사 감지:      {total:>5}건    ║
║  cluster_events 삭제: {deleted_ce:>5}건    ║
║  normalized 삭제:     {deleted_ne:>5}건    ║
║  raw_events 리셋:     {reset_raw:>5}건    ║
╚═══════════════════════════════════╝
→ Worker가 개선된 AI 프롬프트로 재분류합니다.
""")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
