"""conflict→maritime 오분류 원인 조사."""
import asyncio, sys
sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")
from worker.processor.normalizer import _classify_topic, TOPIC_KEYWORDS, _STRONG_KEYWORDS, _kw_in_text

PROD_DB = (
    "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:"
    "WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
)

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(PROD_DB, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        rows = await db.execute(text("""
            SELECT ne.title, ne.body, ne.topic, ne.country_code
            FROM normalized_events ne
            WHERE ne.topic = 'conflict'
              AND ne.title IS NOT NULL AND ne.title != ''
              AND ne.severity > 30
            ORDER BY ne.created_at DESC
            LIMIT 300
        """))
        events = rows.fetchall()
    await engine.dispose()

    maritime_kws = TOPIC_KEYWORDS.get("maritime", [])
    maritime_strong = _STRONG_KEYWORDS.get("maritime", set())

    print(f"로드: {len(events)}개\n")
    print("=== conflict 기사 중 maritime으로 오분류되는 케이스 ===\n")

    count = 0
    for title, body, ai_topic, cc in events:
        text_for_analysis = f"{title or ''} {body or ''}".strip()
        fb_topic = _classify_topic(text_for_analysis)
        if fb_topic == "maritime":
            t = text_for_analysis.lower()
            strong_hits = [k for k in maritime_strong if _kw_in_text(k, t)]
            weak_hits = [k for k in maritime_kws if k not in maritime_strong and _kw_in_text(k, t)]
            print(f"  TITLE: {title[:70]}")
            print(f"  maritime STRONG hit: {strong_hits}")
            print(f"  maritime WEAK hit  : {weak_hits}")
            print()
            count += 1
            if count >= 15:
                break

    print(f"총 {count}건 샘플 확인")

asyncio.run(main())
