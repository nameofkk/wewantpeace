"""
기존 클러스터에 GPT-4o-mini AI 제목 일괄 적용.

실행:
  # dry-run (변경 없이 미리보기)
  DATABASE_URL=... .venv/bin/python3 scripts/ai_retitle.py --dry-run

  # 프로덕션 적용
  DATABASE_URL=... .venv/bin/python3 scripts/ai_retitle.py
"""
import asyncio
import sys
import time

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal
from worker.processor.ai_title import generate_ai_title

DRY_RUN = "--dry-run" in sys.argv


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
        r = await db.execute(text("""
            SELECT id, title, title_ko, topic, country_code
            FROM issue_clusters
            WHERE severity > 0
              AND (title_ko IS NULL
                   OR title_ko = ''
                   OR title_ko = title
                   OR title_ko ~ E'^\\[.+\\]'
                   OR title_ko LIKE '%습니다%'
                   OR title_ko LIKE '%입니다%'
                   OR length(title_ko) > 50)
            ORDER BY id
        """))
        clusters = r.fetchall()
        total = len(clusters)
        print(f"재처리 대상 {total}개 클러스터 (dry_run={DRY_RUN})")

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

            result = generate_ai_title(event_titles, topic, country_code)

            if result:
                new_en, new_ko = result
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


if __name__ == "__main__":
    asyncio.run(main())
