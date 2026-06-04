"""
기존 클러스터에 AI 제목 일괄 적용.

실행:
  # dry-run (변경 없이 미리보기)
  DATABASE_URL=... .venv/bin/python3 scripts/ai_retitle.py --dry-run

  # 프로덕션 적용 (전체)
  DATABASE_URL=... .venv/bin/python3 scripts/ai_retitle.py

  # 배치 제한 (100개만)
  DATABASE_URL=... .venv/bin/python3 scripts/ai_retitle.py --limit 100
"""
import asyncio
import sys
import time

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal
from worker.processor.ai_title import generate_ai_title
from worker.processor.clusterer import _fix_translation_style

DRY_RUN = "--dry-run" in sys.argv

# --limit N 파싱
LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


def _generate_with_retry(events, topic, country_code, max_retries=3):
    """rate limit 429 시 대기 후 재시도."""
    import openai
    for attempt in range(max_retries):
        try:
            return generate_ai_title(events, topic, country_code)
        except openai.RateLimitError as e:
            if attempt == max_retries - 1:
                print(f"  ⚠ RateLimit 최대 재시도 초과, 건너뜀")
                return None
            # 에러 메시지에서 대기 시간 파싱
            wait = 65
            import re
            m = re.search(r"try again in (\d+)m([\d.]+)s", str(e))
            if m:
                wait = int(m.group(1)) * 60 + float(m.group(2)) + 2
            print(f"  ⏳ RateLimit — {wait:.0f}초 대기 후 재시도 ({attempt+1}/{max_retries})")
            time.sleep(wait)
        except Exception:
            return None
    return None


async def main():
    updated = 0
    skipped = 0
    failed = 0

    async with AsyncSessionLocal() as db:
        # 나쁜 품질 title_ko를 가진 클러스터 재처리:
        # 1) title_ko 없음 / 비어있음 / 영문과 동일
        # 2) [국가] 접두사 패턴 (reprocess_topics.py가 생성)
        # 3) 직역체 종결어미 (습니다/입니다)
        # 4) 50자 초과 (너무 김)
        # 5) 8자 미만 (잘못된 번역 — "승천에" 3자 등)
        r = await db.execute(text("""
            SELECT id, title, title_ko, topic, country_code
            FROM issue_clusters
            WHERE severity > 0
              AND (title_ko IS NULL
                   OR title_ko = ''
                   OR title_ko = title
                   OR title_ko LIKE '[%'
                   OR title_ko LIKE '#%'
                   OR title_ko LIKE '%습니다%'
                   OR title_ko LIKE '%입니다%'
                   OR title_ko LIKE '%합니다%'
                   OR title_ko LIKE '%됩니다%'
                   OR title_ko LIKE '%봅니다%'
                   OR title_ko LIKE '%습니까%'
                   OR title_ko LIKE '%합니까%'
                   OR title_ko ~ '에\s+따르면'
                   OR length(title_ko) > 50
                   OR length(title_ko) < 8)
            ORDER BY is_active DESC, kscore DESC, id
        """))
        all_clusters = r.fetchall()
        clusters = all_clusters[:LIMIT] if LIMIT else all_clusters
        total = len(clusters)
        print(f"재처리 대상 {total}개 클러스터 (전체={len(all_clusters)}, limit={LIMIT}, dry_run={DRY_RUN})")

        for i, row in enumerate(clusters):
            cid, title, title_ko, topic, country_code = row

            # 소속 이벤트 제목 조회 (최대 5개)
            ev_r = await db.execute(text("""
                SELECT ne.title
                FROM cluster_events ce
                JOIN normalized_events ne ON ne.id = ce.event_id
                WHERE ce.cluster_id = :cid
                ORDER BY ne.event_time DESC
                LIMIT 5
            """), {"cid": cid})
            event_titles = [{"title": r[0]} for r in ev_r.fetchall() if r[0]]

            if not event_titles:
                event_titles = [{"title": title}] if title else []

            if not event_titles:
                skipped += 1
                continue

            result = _generate_with_retry(event_titles, topic, country_code)

            if result:
                new_en, new_ko = result
                new_ko = _fix_translation_style(new_ko) if new_ko else new_ko
                if DRY_RUN:
                    print(f"[{i+1}/{total}] #{cid}")
                    print(f"  기존: {title[:60]}")
                    print(f"  → EN: {new_en}")
                    print(f"  → KO: {new_ko}")
                    print()
                else:
                    await db.execute(text("""
                        UPDATE issue_clusters
                        SET title = :title_en, title_ko = :title_ko
                        WHERE id = :cid
                    """), {"title_en": new_en, "title_ko": new_ko, "cid": cid})
                    await db.commit()
                updated += 1
            else:
                failed += 1

            # rate limit 방지
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

            if (i + 1) % 50 == 0:
                print(f"  진행: {i+1}/{total} (성공={updated}, 실패={failed}, 건너뜀={skipped})")

        if not DRY_RUN:
            await db.commit()

    print(f"\n완료: 총={total}, 업데이트={updated}, 실패={failed}, 건너뜀={skipped}")

    # trending_keywords 동기화 (keyword/keyword_ko를 issue_clusters와 맞춤)
    if not DRY_RUN and updated > 0:
        async with AsyncSessionLocal() as db:
            r = await db.execute(text(
                "UPDATE trending_keywords tk "
                "SET keyword_ko = ic.title_ko, keyword = ic.title "
                "FROM issue_clusters ic "
                "WHERE ic.id = (tk.cluster_ids)[1] "
                "  AND (tk.keyword_ko IS DISTINCT FROM ic.title_ko "
                "       OR tk.keyword IS DISTINCT FROM ic.title) "
                "RETURNING tk.id"
            ))
            synced = len(r.fetchall())
            await db.commit()
            print(f"trending_keywords 동기화: {synced}건")

        # Redis 캐시 삭제 (즉시 반영)
        try:
            from backend.app.core.redis import get_redis
            redis = get_redis()
            await redis.delete("trending:global:v1")
            print("Redis 캐시 삭제 완료")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
