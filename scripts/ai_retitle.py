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
        # 활성 클러스터 조회 (severity > 0)
        r = await db.execute(text("""
            SELECT id, title, title_ko, topic, country_code
            FROM issue_clusters
            WHERE severity > 0
            ORDER BY id
        """))
        clusters = r.fetchall()
        total = len(clusters)
        print(f"총 {total}개 클러스터 처리 시작 (dry_run={DRY_RUN})")

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
                # 이벤트 제목이 없으면 클러스터 제목만 사용
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
                    if (i + 1) % 50 == 0:
                        await db.commit()
                        print(f"  [{i+1}/{total}] 커밋 완료")
                updated += 1
            else:
                failed += 1

            # rate limit 방지
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

            if (i + 1) % 100 == 0:
                print(f"  진행: {i+1}/{total} (성공={updated}, 실패={failed}, 건너뜀={skipped})")

        if not DRY_RUN:
            await db.commit()

    print(f"\n완료: 총={total}, 업데이트={updated}, 실패={failed}, 건너뜀={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
