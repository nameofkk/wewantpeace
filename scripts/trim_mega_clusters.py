"""기간이 수명 상한을 크게 넘은 활성 클러스터를 최근 이벤트만 남기고 잘라낸다 (1회성).

트렌딩 배치 병합이 거대 클러스터를 날마다 새 클러스터로 옮겨 담으면서, 9월 이슈에
3월 이벤트까지 1,000건 넘게 붙어 있었다. 병합 조건은 코드에서 고쳤고(can_merge_clusters),
이 스크립트는 이미 부풀어 있는 클러스터를 정리한다.

- 대상: 활성 + (last_event_at - first_event_at) > 14일
- 남기는 것: last_event_at 기준 MAX_CLUSTER_AGE_HOURS(5일) 안의 이벤트
- 나머지는 cluster_events 연결만 끊는다 (normalized_events 는 그대로)
- event_count / first_event_at / window_start / severity / source_tiers 재계산
  (kscore·independent_sources 는 5분 주기 트렌딩 배치가 다시 계산)

새 병합 코드가 배포된 뒤에 돌려야 한다 — 옛 코드가 돌고 있으면 다시 합쳐진다.

사용:
    python scripts/trim_mega_clusters.py            # 조회만
    python scripts/trim_mega_clusters.py --apply    # 실제 반영
"""
import asyncio
import os
import sys
from datetime import timedelta

import asyncpg

# worker/processor/clusterer.py 와 같은 값 (배포 전 컨테이너에서도 돌 수 있게 독립 실행)
MAX_CLUSTER_AGE_HOURS = 120
SEVERITY_HALF_LIFE_HOURS = 48
SPAN_DAYS = 14


def decayed_severity(current, at, now):
    hours = max(0.0, (now - at).total_seconds() / 3600)
    return int(round(current * 0.5 ** (hours / SEVERITY_HALF_LIFE_HOURS)))


async def main(apply: bool) -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        clusters = await conn.fetch(
            """
            SELECT id, title, event_count, first_event_at, last_event_at, severity
            FROM issue_clusters
            WHERE is_active AND last_event_at - first_event_at > make_interval(days => $1)
            ORDER BY event_count DESC
            """,
            SPAN_DAYS,
        )
        print(f"대상 {len(clusters)}개 (기간 {SPAN_DAYS}일 초과 활성)")
        total_unlinked = 0
        for c in clusters:
            events = await conn.fetch(
                """
                SELECT ne.id, ne.event_time, ne.severity, ne.source_tier
                FROM cluster_events ce JOIN normalized_events ne ON ne.id = ce.event_id
                WHERE ce.cluster_id = $1
                """,
                c["id"],
            )
            if not events:
                continue
            # 기준은 실제로 연결된 최신 이벤트 — last_event_at 은 병합 과정에서 어긋난 경우가 있다
            keep_from = max(e["event_time"] for e in events) - timedelta(hours=MAX_CLUSTER_AGE_HOURS)
            keep = [e for e in events if e["event_time"] >= keep_from]
            drop = [e for e in events if e["event_time"] < keep_from]
            if not keep:
                print(f"  건너뜀(남길 이벤트 없음) {c['id']} {c['title'][:50]}")
                continue
            last_at = max(e["event_time"] for e in keep)
            first_at = min(e["event_time"] for e in keep)
            severity = max(decayed_severity(e["severity"], e["event_time"], last_at) for e in keep)
            tiers = [e["source_tier"] for e in keep if e["source_tier"]]
            print(
                f"  {c['event_count']:>5} → {len(keep):>4}건  sev {c['severity']:>3} → {severity:>3}  "
                f"{c['first_event_at']:%m-%d}~{c['last_event_at']:%m-%d} → {first_at:%m-%d}~{last_at:%m-%d}  "
                f"{c['title'][:50]}"
            )
            total_unlinked += len(drop)
            if not apply:
                continue
            async with conn.transaction():
                # 되돌릴 수 있게 끊는 연결을 먼저 백업 표에 남긴다 (DB 안이라 재배포에도 남는다)
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS cluster_events_trim_bak "
                    "(cluster_id uuid, event_id uuid, trimmed_at timestamptz DEFAULT now())"
                )
                await conn.execute(
                    "INSERT INTO cluster_events_trim_bak (cluster_id, event_id) "
                    "SELECT $1, unnest($2::uuid[])",
                    c["id"], [e["id"] for e in drop],
                )
                await conn.execute(
                    "DELETE FROM cluster_events WHERE cluster_id = $1 AND event_id = ANY($2::uuid[])",
                    c["id"], [e["id"] for e in drop],
                )
                await conn.execute(
                    """
                    UPDATE issue_clusters
                    SET event_count = $2, first_event_at = $3, window_start = $3, last_event_at = $6,
                        severity = $4, source_tiers = $5, updated_at = now()
                    WHERE id = $1
                    """,
                    c["id"], len(keep), first_at, severity, tiers, last_at,
                )
        print(f"연결 해제 이벤트 합계: {total_unlinked}건 ({'반영함' if apply else '조회만, --apply 로 반영'})")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
