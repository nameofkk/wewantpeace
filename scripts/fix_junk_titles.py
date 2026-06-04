"""
클러스터 쓰레기 제목 수정.

해시태그만 있거나 의미 없는 제목을 가진 issue_clusters를 찾아
같은 topic+country의 normalized_events에서 가장 좋은 제목으로 교체.

실행:
  python3 scripts/fix_junk_titles.py           # dry-run (확인만)
  python3 scripts/fix_junk_titles.py --apply   # 실제 수정
"""
import asyncio
import re
import sys

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal


def is_junk(title: str) -> bool:
    """해시태그만 있거나 의미 없는 제목인지 판별."""
    stripped = re.sub(r'#\w+', '', title).strip()
    return len(stripped) < 5


def translate_title(title: str) -> str | None:
    """영어 → 한국어 번역."""
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="ko").translate(title[:200])
    except Exception:
        return None


async def main():
    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== 클러스터 쓰레기 제목 수정 ({mode}) ===\n")

    async with AsyncSessionLocal() as db:
        # 1. 모든 활성 클러스터 조회
        result = await db.execute(text("""
            SELECT id, title, title_ko, topic, country_code,
                   cluster_key, window_start, window_end
            FROM issue_clusters
            WHERE severity > 0
            ORDER BY last_event_at DESC
        """))
        clusters = result.fetchall()

        junk_count = 0
        fixed_count = 0

        for c in clusters:
            cid, title, title_ko, topic, country_code, cluster_key, w_start, w_end = c

            if not is_junk(title):
                continue

            junk_count += 1

            # 같은 topic+country+시간범위의 이벤트에서 좋은 제목 찾기
            ev_result = await db.execute(text("""
                SELECT title FROM normalized_events
                WHERE topic = :topic
                  AND (:cc IS NULL OR country_code = :cc)
                  AND event_time BETWEEN :ws AND :we
                ORDER BY severity DESC, confidence DESC
                LIMIT 20
            """), {"topic": topic, "cc": country_code, "ws": w_start, "we": w_end})
            events = ev_result.fetchall()

            # 가장 긴 non-junk 제목 선택
            best_title = None
            for ev in events:
                if not is_junk(ev[0]) and len(ev[0]) > len(best_title or ""):
                    best_title = ev[0]

            if not best_title:
                print(f"  ✗ [{country_code or '??'}] {title[:40]} → 대체 제목 없음")
                continue

            # 한국어 번역
            best_ko = translate_title(best_title)
            # 70자 초과 시 자르기
            if best_ko and len(best_ko) > 70:
                best_ko = best_ko[:68] + "…"

            print(f"  ✓ [{country_code or '??'}] {title[:30]} → {best_title[:50]}")
            if best_ko:
                print(f"    KO: {best_ko[:60]}")

            if apply:
                await db.execute(text("""
                    UPDATE issue_clusters
                    SET title = :new_title, title_ko = :new_ko
                    WHERE id = :cid
                """), {"new_title": best_title, "new_ko": best_ko, "cid": cid})
                fixed_count += 1

        if apply:
            await db.commit()

        print(f"\n총 {len(clusters)}개 클러스터 중 쓰레기 제목 {junk_count}개")
        if apply:
            print(f"수정 완료: {fixed_count}개")
        else:
            print("--apply 옵션으로 실제 수정하세요.")


if __name__ == "__main__":
    asyncio.run(main())
