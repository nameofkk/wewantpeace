"""
같은 cluster_key를 가진 분산 클러스터를 일괄 병합.

각 cluster_key 그룹에서 KScore가 가장 높은 클러스터를 winner로 선택,
나머지 loser의 이벤트를 winner에 합류시키고 loser를 severity=0으로 비활성화.

실행:
  DATABASE_URL=... .venv/bin/python3 scripts/merge_clusters.py --dry-run
  DATABASE_URL=... .venv/bin/python3 scripts/merge_clusters.py
"""
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text, select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.issue_cluster import IssueCluster
from worker.processor.trending_engine import _calc_kscore

DRY_RUN = "--dry-run" in sys.argv


async def main():
    merged_total = 0
    groups_merged = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IssueCluster).where(
                IssueCluster.severity > 0,
            ).order_by(
                IssueCluster.cluster_key,
                IssueCluster.kscore.desc(),
            )
        )
        clusters = result.scalars().all()

        groups: dict[str, list] = defaultdict(list)
        for c in clusters:
            groups[c.cluster_key].append(c)

        fragmented = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"총 {len(groups)}개 클러스터 키, {len(fragmented)}개 키에 분산 발생")
        print(f"분산 클러스터 총: {sum(len(v) for v in fragmented.values())}개")
        print()

        for key, group in sorted(fragmented.items(), key=lambda x: len(x[1]), reverse=True):
            winner = group[0]  # KScore 최고
            losers = group[1:]

            if DRY_RUN:
                print(f"[{key}] {len(group)}개 → 1개로 병합")
                print(f"  winner: {(winner.title_ko or winner.title)[:50]} (ks={winner.kscore:.1f})")
                for l in losers[:3]:
                    print(f"  loser:  {(l.title_ko or l.title)[:50]} (ks={l.kscore:.1f})")
                if len(losers) > 3:
                    print(f"  ... 외 {len(losers)-3}개")
                print()
                groups_merged += 1
                merged_total += len(losers)
                continue

            for loser in losers:
                winner.event_count += loser.event_count
                winner.independent_sources = (winner.independent_sources or 1) + (loser.independent_sources or 1)
                if loser.severity > winner.severity:
                    winner.severity = loser.severity
                winner.confidence = round(max(winner.confidence, loser.confidence), 3)
                existing = list(winner.source_tiers or [])
                existing.extend(loser.source_tiers or [])
                winner.source_tiers = existing
                if loser.first_event_at and (not winner.first_event_at or loser.first_event_at < winner.first_event_at):
                    winner.first_event_at = loser.first_event_at
                if loser.last_event_at and (not winner.last_event_at or loser.last_event_at > winner.last_event_at):
                    winner.last_event_at = loser.last_event_at
                    winner.window_end = loser.last_event_at + timedelta(minutes=60)

                # cluster_events 재할당
                await db.execute(
                    text("UPDATE cluster_events SET cluster_id = :w WHERE cluster_id = :l"),
                    {"w": winner.id, "l": loser.id},
                )
                loser.severity = 0
                loser.kscore = 0
                merged_total += 1

            # winner KScore 재계산
            winner.kscore, _ = _calc_kscore(
                event_count=winner.event_count,
                is_spike=winner.is_spike,
                confidence=winner.confidence,
                severity=winner.severity,
                independent_sources=winner.independent_sources or 1,
                source_tiers=winner.source_tiers or [],
            )
            winner.updated_at = datetime.now(timezone.utc)
            groups_merged += 1

            if groups_merged % 50 == 0:
                await db.commit()
                print(f"  진행: {groups_merged}개 그룹 처리, {merged_total}개 병합")

        if not DRY_RUN:
            await db.commit()

            # trending_keywords 동기화
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

            # 비활성화된 클러스터의 trending 삭제
            r2 = await db.execute(text(
                "DELETE FROM trending_keywords tk "
                "WHERE EXISTS ("
                "  SELECT 1 FROM issue_clusters ic "
                "  WHERE ic.id = (tk.cluster_ids)[1] AND ic.severity = 0"
                ") RETURNING tk.id"
            ))
            deleted = len(r2.fetchall())
            await db.commit()
            print(f"비활성 trending 삭제: {deleted}건")

            # Redis 캐시 삭제
            try:
                from backend.app.core.redis import get_redis
                redis = get_redis()
                await redis.delete("trending:global:v1")
                print("Redis 캐시 삭제 완료")
            except Exception:
                pass

    print(f"\n완료: {groups_merged}개 그룹에서 {merged_total}개 클러스터 병합 (dry_run={DRY_RUN})")


if __name__ == "__main__":
    asyncio.run(main())
