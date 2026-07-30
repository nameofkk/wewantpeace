"""
Worker 시작 시 누락된 DB 인덱스를 생성.
실패해도 worker 시작은 계속됨 (|| true).
"""
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    import asyncpg

    raw_url = os.environ.get("DATABASE_URL", "")
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
    if not url:
        logger.warning("DATABASE_URL 없음, 인덱스 생성 건너뜀")
        return

    try:
        conn = await asyncpg.connect(url, timeout=20)
    except Exception as e:
        logger.warning("DB 연결 실패 (인덱스 생성 건너뜀): %s", e)
        return

    indexes = [
        # clusterer.py 핵심 쿼리: WHERE cluster_key=? AND window_end>=? ORDER BY last_event_at DESC
        (
            "idx_ic_key_window_lastev",
            "CREATE INDEX IF NOT EXISTS idx_ic_key_window_lastev "
            "ON issue_clusters (cluster_key, window_end DESC, last_event_at DESC)",
        ),
        # /public/weekly-summary의 주간 카운트가 Seq Scan을 타고 있었다.
        # EXPLAIN ANALYZE 실측: normalized_events 410ms, issue_clusters 931ms
        # (weekly-summary는 이 카운트를 이번 주/전주로 각각 2번씩 = 4회 실행)
        (
            "idx_ne_created_at",
            "CREATE INDEX IF NOT EXISTS idx_ne_created_at "
            "ON normalized_events (created_at DESC)",
        ),
        (
            "idx_ic_first_event_at",
            "CREATE INDEX IF NOT EXISTS idx_ic_first_event_at "
            "ON issue_clusters (first_event_at DESC)",
        ),
    ]

    for name, sql in indexes:
        try:
            await conn.execute(sql)
            logger.info("인덱스 확인/생성 완료: %s", name)
        except Exception as e:
            logger.warning("인덱스 생성 실패 (%s): %s", name, e)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
