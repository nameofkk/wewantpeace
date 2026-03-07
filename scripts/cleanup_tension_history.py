"""
긴장도/KScore 히스토리 스파이크 데이터 정리.

재클러스터링(3/7~8) 후 비정상 스파이크 제거.
전후(3/5~6, 3/9~10) 평균 대비 2배 이상인 레코드를 식별하여 삭제.

실행:
  python3 scripts/cleanup_tension_history.py --dry-run   # 확인만
  python3 scripts/cleanup_tension_history.py --execute    # 실제 삭제
"""
import asyncio
import sys

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal


SPIKE_START = "2026-03-07 00:00:00+09"
SPIKE_END = "2026-03-09 00:00:00+09"
BEFORE_START = "2026-03-05 00:00:00+09"
BEFORE_END = "2026-03-07 00:00:00+09"
AFTER_START = "2026-03-09 00:00:00+09"
AFTER_END = "2026-03-11 00:00:00+09"

DRY_RUN = "--dry-run" in sys.argv
EXECUTE = "--execute" in sys.argv

if not DRY_RUN and not EXECUTE:
    print("사용법: python3 scripts/cleanup_tension_history.py [--dry-run | --execute]")
    sys.exit(1)


async def main():
    async with AsyncSessionLocal() as db:
        # 1. 전후 기간 평균 raw_score (country_code별)
        avg_result = await db.execute(text("""
            SELECT country_code,
                   AVG(raw_score) as avg_score,
                   STDDEV(raw_score) as std_score,
                   COUNT(*) as cnt
            FROM tension_index
            WHERE (time >= :before_start AND time < :before_end)
               OR (time >= :after_start AND time < :after_end)
            GROUP BY country_code
        """), {
            "before_start": BEFORE_START,
            "before_end": BEFORE_END,
            "after_start": AFTER_START,
            "after_end": AFTER_END,
        })
        baselines = {}
        for row in avg_result.fetchall():
            avg = row.avg_score or 0
            std = row.std_score or 0
            # 임계값: 평균 + 2*표준편차, 최소 평균의 2배
            threshold = max(avg + 2 * std, avg * 2) if avg > 0 else 999
            baselines[row.country_code] = {
                "avg": avg, "std": std, "threshold": threshold, "cnt": row.cnt,
            }

        print(f"[Step 1] 기준 기간 국가 수: {len(baselines)}")
        for cc, info in sorted(baselines.items()):
            print(f"  {cc}: avg={info['avg']:.2f}, std={info['std']:.2f}, threshold={info['threshold']:.2f}")

        # 2. 스파이크 기간 레코드 조회
        spike_result = await db.execute(text("""
            SELECT time, country_code, raw_score, tension_level,
                   event_score, accel_score, spillover_score
            FROM tension_index
            WHERE time >= :start AND time < :end
            ORDER BY country_code, time
        """), {"start": SPIKE_START, "end": SPIKE_END})
        spike_rows = spike_result.fetchall()

        print(f"\n[Step 2] 스파이크 기간({SPIKE_START} ~ {SPIKE_END}) 레코드: {len(spike_rows)}건")

        # 3. 비정상 스파이크 식별
        to_delete = []
        normal_count = 0
        no_baseline_count = 0
        for row in spike_rows:
            cc = row.country_code
            if cc not in baselines:
                # 스파이크 기간에만 존재하는 country_code → 스파이크로 간주
                to_delete.append(row)
                no_baseline_count += 1
                continue

            threshold = baselines[cc]["threshold"]
            if row.raw_score > threshold:
                to_delete.append(row)
            else:
                normal_count += 1

        print(f"\n[Step 3] 분석 결과:")
        print(f"  정상 레코드: {normal_count}건")
        print(f"  스파이크 레코드 (임계값 초과): {len(to_delete) - no_baseline_count}건")
        print(f"  스파이크 레코드 (기준 없음): {no_baseline_count}건")
        print(f"  총 삭제 대상: {len(to_delete)}건")

        if to_delete:
            print(f"\n[상세] 삭제 대상:")
            for r in to_delete[:20]:
                bl = baselines.get(r.country_code, {})
                print(f"  {r.time} | {r.country_code} | raw={r.raw_score:.2f} | "
                      f"threshold={bl.get('threshold', 'N/A')}")
            if len(to_delete) > 20:
                print(f"  ... 외 {len(to_delete) - 20}건")

        # 4. 삭제 실행
        if EXECUTE and to_delete:
            delete_count = await db.execute(text("""
                DELETE FROM tension_index
                WHERE time >= :start AND time < :end
                  AND raw_score > (
                      SELECT GREATEST(
                          COALESCE(AVG(t2.raw_score), 0) + 2 * COALESCE(STDDEV(t2.raw_score), 0),
                          COALESCE(AVG(t2.raw_score), 0) * 2
                      )
                      FROM tension_index t2
                      WHERE t2.country_code = tension_index.country_code
                        AND ((t2.time >= :before_start AND t2.time < :before_end)
                          OR (t2.time >= :after_start AND t2.time < :after_end))
                  )
            """), {
                "start": SPIKE_START,
                "end": SPIKE_END,
                "before_start": BEFORE_START,
                "before_end": BEFORE_END,
                "after_start": AFTER_START,
                "after_end": AFTER_END,
            })
            # 기준 없는 레코드도 삭제
            if no_baseline_count > 0:
                await db.execute(text("""
                    DELETE FROM tension_index
                    WHERE time >= :start AND time < :end
                      AND country_code NOT IN (
                          SELECT DISTINCT country_code FROM tension_index
                          WHERE (time >= :before_start AND time < :before_end)
                             OR (time >= :after_start AND time < :after_end)
                      )
                """), {
                    "start": SPIKE_START,
                    "end": SPIKE_END,
                    "before_start": BEFORE_START,
                    "before_end": BEFORE_END,
                    "after_start": AFTER_START,
                    "after_end": AFTER_END,
                })
            await db.commit()
            print(f"\n✅ 삭제 완료! tension calculator가 다음 주기에 자동 재계산합니다.")
        elif DRY_RUN:
            print(f"\n🔍 DRY RUN — 삭제 실행 안 함. --execute 옵션으로 실행하세요.")
        else:
            print(f"\n삭제 대상 없음.")


if __name__ == "__main__":
    asyncio.run(main())
