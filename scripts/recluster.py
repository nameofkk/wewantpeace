"""
전체 재클러스터링 스크립트 (v6: Filtered Jaccard + 24h 윈도우).

**Raw SQL 전용** — ORM identity map/autoflush 문제 완전 제거.
Supabase Pooler 대응: 배치마다 DB 연결 재생성.
"""
import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DRY_RUN = "--dry-run" in sys.argv
WITH_AI = "--with-ai" in sys.argv
DB_URL = os.environ.get("DATABASE_URL", "")

RESUME_FROM = 0
for i, arg in enumerate(sys.argv):
    if arg == "--resume" and i + 1 < len(sys.argv):
        RESUME_FROM = int(sys.argv[i + 1])

BATCH_SIZE = 200
WINDOW_MINUTES = 1440  # 24h
MIN_TITLE_OVERLAP = 0.15
MIN_TITLE_OVERLAP_HIGH_SEV = 0.08
MAX_CANDIDATE_CLUSTERS = 20
MAX_EVENTS_UNKNOWN_GEO = 100

if not DB_URL:
    print("ERROR: DATABASE_URL 환경변수 필요")
    sys.exit(1)

# ── Filtered Jaccard 유사도 (clusterer.py에서 복사) ────────────────────────

from worker.processor.clusterer import (
    _title_similarity,
    _cluster_key,
    _make_cluster_title_ko,
    _make_fallback_titles,
    _is_junk_title,
)
from worker.processor.trending_engine import _calc_kscore
from worker.processor.ai_title import generate_ai_title


def _make_engine():
    return create_async_engine(
        DB_URL,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": 120,
            "server_settings": {"statement_timeout": "120000"},
        },
    )


async def _exec(engine, sql, params=None):
    """단일 쿼리 실행 후 연결 반환."""
    async with engine.connect() as conn:
        r = await conn.execute(text(sql), params or {})
        await conn.commit()
        return r


async def _delete_all(engine):
    """기존 cluster_events + issue_clusters 전부 삭제."""
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM issue_clusters"))
        old_clusters = r.scalar()
        r = await conn.execute(text("SELECT COUNT(*) FROM cluster_events"))
        old_mappings = r.scalar()
        await conn.commit()

    print(f"  기존 클러스터: {old_clusters:,}개, 매핑: {old_mappings:,}개")

    print("[Step 1] cluster_events 배치 삭제...")
    total_ce = 0
    while True:
        async with engine.connect() as conn:
            r = await conn.execute(text(
                "DELETE FROM cluster_events WHERE cluster_id IN "
                "(SELECT DISTINCT cluster_id FROM cluster_events LIMIT 100)"
            ))
            deleted = r.rowcount
            await conn.commit()
        if deleted == 0:
            break
        total_ce += deleted
        if total_ce % 500 == 0 or deleted < 100:
            print(f"  cluster_events: {total_ce:,}/{old_mappings:,}")
    print(f"  cluster_events 삭제 완료: {total_ce:,}건")

    print("[Step 1b] issue_clusters 배치 삭제...")
    total_ic = 0
    while True:
        async with engine.connect() as conn:
            r = await conn.execute(text(
                "DELETE FROM issue_clusters WHERE id IN "
                "(SELECT id FROM issue_clusters LIMIT 500)"
            ))
            deleted = r.rowcount
            await conn.commit()
        if deleted == 0:
            break
        total_ic += deleted
        print(f"  issue_clusters: {total_ic:,}/{old_clusters:,}")
    print(f"  issue_clusters 삭제 완료: {total_ic:,}건")

    return old_clusters, old_mappings


async def _load_events(engine) -> list[dict]:
    """이벤트 목록 로드 → dict 리스트."""
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT id, title, title_ko, body, topic, entity_anchor,
                   country_code, lat, lon, geohash5, severity,
                   source_tier, confidence, image_url, event_time
            FROM normalized_events
            WHERE severity >= 20
              AND NOT (topic = 'unknown' AND severity <= 25)
              AND is_duplicate = false
            ORDER BY event_time ASC
        """))
        columns = ["id", "title", "title_ko", "body", "topic", "entity_anchor",
                    "country_code", "lat", "lon", "geohash5", "severity",
                    "source_tier", "confidence", "image_url", "event_time"]
        rows = [dict(zip(columns, row)) for row in r.fetchall()]
        await conn.commit()
    return rows


def _event_cluster_key(event: dict) -> str:
    """cluster_key 생성 (cluster.py의 _cluster_key와 동일)."""
    cc = event.get("country_code") or ""
    gh = event.get("geohash5") or ""
    topic = event.get("topic") or "unknown"
    if cc:
        return f"{cc}:{topic}"
    if gh:
        return f"{gh[:4]}:{topic}"
    return f"0000:{topic}"


async def _process_batch(events: list[dict], start: int, end: int, stats: dict):
    """배치 처리: raw SQL로 클러스터 매칭/생성/업데이트."""
    engine = _make_engine()
    now = datetime.now(timezone.utc)

    for i in range(start, min(end, len(events))):
        ev = events[i]
        key = _event_cluster_key(ev)
        window_cutoff = ev["event_time"] - timedelta(minutes=WINDOW_MINUTES)

        try:
            async with engine.connect() as conn:
                # 1. 윈도우 내 후보 클러스터 조회
                r = await conn.execute(text("""
                    SELECT id, title, title_ko, severity, event_count,
                           confidence, source_tiers, independent_sources,
                           is_spike, last_event_at, country_code, geohash5,
                           lat, lon, image_url, is_verified, entity_anchor,
                           first_event_at, window_start, kscore, topic
                    FROM issue_clusters
                    WHERE cluster_key = :key AND window_end >= :evt
                    ORDER BY last_event_at DESC
                    LIMIT :lim
                """), {"key": key, "evt": ev["event_time"], "lim": MAX_CANDIDATE_CLUSTERS})

                candidates = r.fetchall()
                cand_cols = ["id", "title", "title_ko", "severity", "event_count",
                             "confidence", "source_tiers", "independent_sources",
                             "is_spike", "last_event_at", "country_code", "geohash5",
                             "lat", "lon", "image_url", "is_verified", "entity_anchor",
                             "first_event_at", "window_start", "kscore", "topic"]
                candidates = [dict(zip(cand_cols, c)) for c in candidates]

                # 2. Filtered Jaccard로 최적 매칭
                best_cluster = None
                best_sim = -1.0

                for cand in candidates:
                    no_country = not ev.get("country_code")
                    no_geo = not ev.get("geohash5")
                    if no_country and no_geo and cand["event_count"] >= MAX_EVENTS_UNKNOWN_GEO:
                        continue

                    sim = _title_similarity(
                        ev["title"], cand["title"],
                        ko_a=ev.get("title_ko"),
                        ko_b=cand.get("title_ko"),
                    )

                    threshold = MIN_TITLE_OVERLAP_HIGH_SEV \
                        if ev["severity"] >= 50 and cand["severity"] >= 50 \
                        else MIN_TITLE_OVERLAP

                    if sim >= threshold and sim > best_sim:
                        best_sim = sim
                        best_cluster = cand

                if best_cluster:
                    # 3a. 기존 클러스터에 병합 (UPDATE + INSERT)
                    n = best_cluster["event_count"]
                    new_count = n + 1
                    new_conf = round((best_cluster["confidence"] * n + ev["confidence"]) / new_count, 3)
                    new_sev = max(best_cluster["severity"], ev["severity"])
                    tiers = list(best_cluster["source_tiers"] or [])
                    if ev.get("source_tier"):
                        tiers.append(ev["source_tier"])
                    new_window_end = ev["event_time"] + timedelta(minutes=WINDOW_MINUTES)

                    # KScore 재계산
                    age_hours = (now - ev["event_time"]).total_seconds() / 3600
                    kscore, _ = _calc_kscore(
                        event_count=new_count,
                        is_spike=best_cluster["is_spike"],
                        confidence=new_conf,
                        severity=new_sev,
                        independent_sources=best_cluster["independent_sources"] or 1,
                        source_tiers=tiers,
                        age_hours=age_hours,
                    )

                    # 제목 업그레이드
                    new_title = best_cluster["title"]
                    new_title_ko = best_cluster["title_ko"]
                    if _is_junk_title(best_cluster["title"]) and not _is_junk_title(ev["title"]):
                        new_title = ev["title"]
                        new_title_ko = _make_cluster_title_ko(ev["title"], ev["topic"], ev.get("country_code"))

                    # image_url
                    new_img = best_cluster["image_url"] or ev.get("image_url")

                    # geo 업데이트
                    new_lat = best_cluster["lat"] if best_cluster["lat"] is not None else ev.get("lat")
                    new_lon = best_cluster["lon"] if best_cluster["lon"] is not None else ev.get("lon")

                    await conn.execute(text("""
                        UPDATE issue_clusters SET
                            event_count = :cnt, confidence = :conf, severity = :sev,
                            source_tiers = :tiers, last_event_at = :last_ev,
                            window_end = :wend, kscore = :ks, updated_at = :now,
                            title = :title, title_ko = :title_ko, image_url = :img,
                            lat = :lat, lon = :lon
                        WHERE id = :cid
                    """), {
                        "cnt": new_count, "conf": new_conf, "sev": new_sev,
                        "tiers": tiers, "last_ev": ev["event_time"],
                        "wend": new_window_end, "ks": kscore, "now": now,
                        "title": new_title, "title_ko": new_title_ko,
                        "img": new_img, "lat": new_lat, "lon": new_lon,
                        "cid": best_cluster["id"],
                    })

                    # ClusterEvent INSERT (ON CONFLICT DO NOTHING)
                    await conn.execute(text("""
                        INSERT INTO cluster_events (cluster_id, event_id)
                        VALUES (:cid, :eid)
                        ON CONFLICT DO NOTHING
                    """), {"cid": best_cluster["id"], "eid": ev["id"]})

                    await conn.commit()
                    stats["merged"] += 1

                else:
                    # 3b. 새 클러스터 생성
                    cluster_id = uuid.uuid4()
                    geohash5 = ev.get("geohash5") or "00000"

                    # 제목 생성
                    title_ko = _make_cluster_title_ko(ev["title"], ev["topic"], ev.get("country_code"))
                    title_en = ev["title"]
                    if _is_junk_title(ev["title"]):
                        fb_en, fb_ko = _make_fallback_titles(ev["topic"], ev.get("country_code"))
                        title_en = fb_en or ev["title"]
                        if fb_ko:
                            title_ko = fb_ko

                    tiers = [ev["source_tier"]] if ev.get("source_tier") else []
                    kscore, _ = _calc_kscore(
                        event_count=1, is_spike=False,
                        confidence=ev["confidence"], severity=ev["severity"],
                        independent_sources=1, source_tiers=tiers,
                    )

                    await conn.execute(text("""
                        INSERT INTO issue_clusters (
                            id, cluster_key, geohash5, topic, entity_anchor,
                            country_code, lat, lon, title, title_ko,
                            event_count, severity, confidence, kscore, is_spike,
                            source_tiers, independent_sources,
                            first_event_at, last_event_at,
                            window_start, window_end,
                            image_url, is_verified, is_active, created_at, updated_at
                        ) VALUES (
                            :id, :key, :gh, :topic, :ea,
                            :cc, :lat, :lon, :title, :title_ko,
                            1, :sev, :conf, :ks, false,
                            :tiers, 1,
                            :evt, :evt,
                            :wstart, :wend,
                            :img, false, true, :now, :now
                        )
                    """), {
                        "id": cluster_id, "key": key, "gh": geohash5,
                        "topic": ev["topic"], "ea": ev.get("entity_anchor"),
                        "cc": ev.get("country_code"), "lat": ev.get("lat"), "lon": ev.get("lon"),
                        "title": title_en, "title_ko": title_ko,
                        "sev": ev["severity"], "conf": ev["confidence"], "ks": kscore,
                        "tiers": tiers,
                        "evt": ev["event_time"],
                        "wstart": window_cutoff,
                        "wend": ev["event_time"] + timedelta(minutes=WINDOW_MINUTES),
                        "img": ev.get("image_url"), "now": now,
                    })

                    await conn.execute(text("""
                        INSERT INTO cluster_events (cluster_id, event_id)
                        VALUES (:cid, :eid)
                        ON CONFLICT DO NOTHING
                    """), {"cid": cluster_id, "eid": ev["id"]})

                    await conn.commit()
                    stats["new"] += 1

                stats["processed"] += 1

        except Exception as e:
            err_str = str(e).lower()
            if "deadlock" in err_str:
                stats["deadlocks"] += 1
                await asyncio.sleep(2)
                stats["processed"] += 1
                stats["skipped"] += 1
            else:
                print(f"  ✗ 이벤트 {i} 에러: {str(e)[:200]}")
                stats["processed"] += 1
                stats["skipped"] += 1

    await engine.dispose()


async def _post_process():
    """Step 5~8: independent_sources, KScore, 노이즈 비활성화, 통계."""
    engine = _make_engine()

    # Step 5: independent_sources 동기화
    print("[Step 5] independent_sources 동기화...")
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT id FROM issue_clusters"))
        all_cluster_ids = [row[0] for row in r.fetchall()]
        await conn.commit()

    for bi in range(0, len(all_cluster_ids), 100):
        batch_ids = all_cluster_ids[bi:bi + 100]
        async with engine.connect() as conn:
            await conn.execute(text("""
                UPDATE issue_clusters ic
                SET independent_sources = sub.src_count
                FROM (
                    SELECT ce.cluster_id, COUNT(DISTINCT re.source_channel_id) as src_count
                    FROM cluster_events ce
                    JOIN normalized_events ne ON ne.id = ce.event_id
                    JOIN raw_events re ON re.id = ne.raw_event_id
                    WHERE ce.cluster_id = ANY(:ids)
                    GROUP BY ce.cluster_id
                ) sub
                WHERE ic.id = sub.cluster_id
            """), {"ids": batch_ids})
            await conn.commit()
    print(f"  {len(all_cluster_ids):,}개 클러스터 독립출처 동기화 완료.")

    # Step 6: KScore 재계산
    print("[Step 6] KScore 재계산...")
    now_utc = datetime.now(timezone.utc)
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT id, event_count, is_spike, confidence, severity,
                   independent_sources, source_tiers, last_event_at
            FROM issue_clusters
        """))
        clusters = r.fetchall()
        await conn.commit()

    kscore_data = []
    for cl in clusters:
        age_hours = (now_utc - cl[7]).total_seconds() / 3600 if cl[7] else 0.0
        tiers = cl[6] if cl[6] else []
        ks, _ = _calc_kscore(
            event_count=cl[1], is_spike=cl[2], confidence=cl[3],
            severity=cl[4], independent_sources=cl[5],
            source_tiers=tiers, age_hours=age_hours,
        )
        kscore_data.append({"ks": ks, "cid": cl[0]})

    for bi in range(0, len(kscore_data), 200):
        batch = kscore_data[bi:bi + 200]
        async with engine.connect() as conn:
            for item in batch:
                await conn.execute(text(
                    "UPDATE issue_clusters SET kscore = :ks WHERE id = :cid"
                ), item)
            await conn.commit()
    print(f"  {len(clusters):,}개 클러스터 KScore 갱신.")

    # Step 7: 노이즈 클러스터 비활성화
    print("[Step 7] 노이즈 클러스터 비활성화...")
    async with engine.connect() as conn:
        await conn.execute(text("""
            UPDATE issue_clusters
            SET is_active = false, severity = 0
            WHERE severity < 20 AND topic = 'unknown'
        """))
        await conn.commit()
    print("  비활성화 완료.")

    # Step 8: 최종 통계
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM issue_clusters"))
        final_clusters = r.scalar()
        r = await conn.execute(text("SELECT COUNT(*) FROM cluster_events"))
        final_mappings = r.scalar()
        r = await conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE event_count = 1) as single,
                   COUNT(*) FILTER (WHERE event_count >= 2) as multi,
                   COUNT(*) FILTER (WHERE event_count >= 5) as five_plus,
                   AVG(event_count)::numeric(10,2) as avg_ev,
                   MAX(event_count) as max_ev,
                   AVG(independent_sources)::numeric(10,2) as avg_src
            FROM issue_clusters
        """))
        s = r.fetchone()
        await conn.commit()

    await engine.dispose()
    return final_clusters, final_mappings, s


async def main():
    t0 = time.time()

    print("=== 재클러스터링 시작 (Raw SQL) ===")
    print(f"  모드: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print(f"  AI 판정: {'ON' if WITH_AI else 'OFF'}")
    print(f"  배치 크기: {BATCH_SIZE}")
    if RESUME_FROM > 0:
        print(f"  재개 위치: {RESUME_FROM}")
    print()

    if DRY_RUN:
        print("DRY RUN 모드 — 종료.")
        return

    engine = _make_engine()

    old_clusters, old_mappings = 0, 0
    if RESUME_FROM == 0:
        old_clusters, old_mappings = await _delete_all(engine)
    else:
        print(f"[Step 1] SKIP (--resume {RESUME_FROM})")

    print("[Step 3] normalized_events 로드...")
    events = await _load_events(engine)
    total = len(events)
    print(f"  {total:,}개 이벤트 로드 완료.")

    await engine.dispose()

    # Step 4: 재클러스터링
    print(f"[Step 4] 재클러스터링 (배치={BATCH_SIZE})...")
    stats = {"processed": 0, "new": 0, "merged": 0, "skipped": 0, "deadlocks": 0}
    start_idx = RESUME_FROM

    while start_idx < total:
        end_idx = min(start_idx + BATCH_SIZE, total)

        await _process_batch(events, start_idx, end_idx, stats)

        elapsed = time.time() - t0
        rate = stats["processed"] / elapsed if elapsed > 0 else 0
        remaining = total - RESUME_FROM - stats["processed"]
        eta = remaining / rate if rate > 0 else 0

        extras = []
        if stats["deadlocks"]:
            extras.append(f"dl:{stats['deadlocks']}")
        if stats["skipped"]:
            extras.append(f"skip:{stats['skipped']}")
        extra_str = f" ({', '.join(extras)})" if extras else ""

        print(f"  {end_idx:,}/{total:,} "
              f"(새:{stats['new']:,} 병합:{stats['merged']:,}{extra_str} "
              f"{rate:.1f}/s ETA:{eta:.0f}s)")

        start_idx = end_idx
        await asyncio.sleep(0.5)

    print(f"\n  재클러스터링 완료: 새 {stats['new']:,}개, 병합 {stats['merged']:,}개"
          f", 건너뜀 {stats['skipped']:,}개")

    # Step 5~8
    final_clusters, final_mappings, s = await _post_process()

    elapsed = time.time() - t0
    print()
    print(f"=== 재클러스터링 완료 ({elapsed:.1f}초) ===")
    print(f"  클러스터: {old_clusters:,} → {final_clusters:,}")
    print(f"  매핑: {old_mappings:,} → {final_mappings:,}")
    if final_clusters and s:
        print(f"  단일이벤트: {s[0]:,} ({s[0]/final_clusters*100:.1f}%)")
        print(f"  2+이벤트: {s[1]:,} ({s[1]/final_clusters*100:.1f}%)")
        print(f"  5+이벤트: {s[2]:,}")
        print(f"  평균 이벤트: {s[3]}")
        print(f"  최대 이벤트: {s[4]}")
        print(f"  평균 독립출처: {s[5]}")


if __name__ == "__main__":
    asyncio.run(main())
