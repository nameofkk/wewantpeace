"""
기존 오염 클러스터 재분리 스크립트.

event_count >= 5인 클러스터에서 제목 유사도가 낮은 이벤트를 감지하여
서브토픽별로 별도 클러스터로 분리한다.

실행:
  # 드라이런 (변경 없이 분석만)
  DATABASE_URL="..." python3 scripts/recluster_existing.py --dry-run

  # 실제 실행
  DATABASE_URL="..." python3 scripts/recluster_existing.py

  # 특정 클러스터만
  DATABASE_URL="..." python3 scripts/recluster_existing.py --cluster-id c838146d-...
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from worker.processor.clusterer import (
    _title_similarity,
    _make_cluster_title_ko,
    _make_fallback_titles,
    _is_junk_title,
    MIN_TITLE_OVERLAP,
    MIN_TITLE_OVERLAP_HIGH_SEV,
)
from worker.processor.trending_engine import _calc_kscore
from worker.processor.ai_title import generate_ai_title

DRY_RUN = "--dry-run" in sys.argv
CLUSTER_ID = None
for i, arg in enumerate(sys.argv):
    if arg == "--cluster-id" and i + 1 < len(sys.argv):
        CLUSTER_ID = sys.argv[i + 1]

# 분리 임계값: 이 값 미만이면 다른 서브토픽으로 판단
SPLIT_THRESHOLD = 0.15
# 최소 그룹 크기: 이보다 작은 그룹은 분리하지 않고 가장 가까운 그룹에 합침
MIN_GROUP_SIZE = 2


def _group_events_by_similarity(events: list[dict]) -> list[list[dict]]:
    """
    이벤트 목록을 제목 유사도로 그룹핑 (greedy single-linkage).
    각 이벤트를 기존 그룹의 대표 제목과 비교하여 가장 유사한 그룹에 할당.
    임계값 미만이면 새 그룹 생성.

    junk 제목(해시태그만 등)은 그룹 대표가 될 수 없고,
    모든 정상 그룹이 형성된 후 가장 가까운 그룹에 합류.
    """
    if not events:
        return []

    # junk 제목 분리
    normal_events = []
    junk_events = []
    for ev in events:
        if _is_junk_title(ev["title"]):
            junk_events.append(ev)
        else:
            normal_events.append(ev)

    groups: list[list[dict]] = []

    for ev in normal_events:
        best_group_idx = -1
        best_sim = -1.0

        for gi, group in enumerate(groups):
            # 그룹 대표 = 첫 번째 이벤트 (가장 먼저 들어온 것)
            rep = group[0]
            sim = _title_similarity(
                ev["title"], rep["title"],
                ko_a=ev.get("title_ko"),
                ko_b=rep.get("title_ko"),
            )
            if sim > best_sim:
                best_sim = sim
                best_group_idx = gi

        threshold = SPLIT_THRESHOLD
        if best_sim >= threshold and best_group_idx >= 0:
            groups[best_group_idx].append(ev)
        else:
            groups.append([ev])

    # 너무 작은 그룹(MIN_GROUP_SIZE 미만)은 가장 가까운 그룹에 합치기
    final_groups = []
    small_events = []
    for g in groups:
        if len(g) >= MIN_GROUP_SIZE:
            final_groups.append(g)
        else:
            small_events.extend(g)

    # 작은 그룹 + junk 이벤트 → 가장 유사한 기존 그룹에 합치기
    orphans = small_events + junk_events
    for ev in orphans:
        best_idx = 0
        best_sim = -1.0
        for gi, group in enumerate(final_groups):
            sim = _title_similarity(
                ev["title"], group[0]["title"],
                ko_a=ev.get("title_ko"),
                ko_b=group[0].get("title_ko"),
            )
            if sim > best_sim:
                best_sim = sim
                best_idx = gi
        if final_groups:
            final_groups[best_idx].append(ev)
        else:
            # 모든 이벤트가 junk이면 하나로 합침
            final_groups.append([ev])

    return final_groups


async def recluster():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL 환경변수 필요")
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # 대상 클러스터 조회
        if CLUSTER_ID:
            r = await db.execute(text("""
                SELECT id, cluster_key, title, title_ko, event_count, severity,
                       topic, country_code, confidence, is_spike, source_tiers,
                       independent_sources, first_event_at, last_event_at,
                       window_start, window_end, geohash5, lat, lon,
                       image_url, is_verified, entity_anchor, kscore
                FROM issue_clusters
                WHERE id = :cid
            """), {"cid": CLUSTER_ID})
        else:
            r = await db.execute(text("""
                SELECT id, cluster_key, title, title_ko, event_count, severity,
                       topic, country_code, confidence, is_spike, source_tiers,
                       independent_sources, first_event_at, last_event_at,
                       window_start, window_end, geohash5, lat, lon,
                       image_url, is_verified, entity_anchor, kscore
                FROM issue_clusters
                WHERE event_count >= 5
                ORDER BY event_count DESC
            """))

        clusters = r.fetchall()
        print(f"대상 클러스터: {len(clusters)}개")

        total_splits = 0
        total_new_clusters = 0

        for cl in clusters:
            cl_id = cl[0]
            cl_key = cl[1]
            cl_title = cl[2]
            cl_title_ko = cl[3]
            cl_event_count = cl[4]
            cl_severity = cl[5]
            cl_topic = cl[6]
            cl_country = cl[7]
            cl_confidence = cl[8]
            cl_is_spike = cl[9]
            cl_source_tiers = cl[10]
            cl_independent_sources = cl[11]
            cl_first_event_at = cl[12]
            cl_last_event_at = cl[13]
            cl_window_start = cl[14]
            cl_window_end = cl[15]
            cl_geohash5 = cl[16]
            cl_lat = cl[17]
            cl_lon = cl[18]
            cl_image_url = cl[19]
            cl_is_verified = cl[20]
            cl_entity_anchor = cl[21]

            # 이 클러스터의 모든 이벤트 조회
            er = await db.execute(text("""
                SELECT ne.id, ne.title, ne.severity, ne.confidence,
                       ne.event_time, ne.source_tier, ne.country_code,
                       ne.geohash5, ne.lat, ne.lon, ne.image_url,
                       ne.body, ne.topic, ne.entity_anchor
                FROM normalized_events ne
                JOIN cluster_events ce ON ce.event_id = ne.id
                WHERE ce.cluster_id = :cid
                ORDER BY ne.event_time
            """), {"cid": str(cl_id)})
            events = er.fetchall()

            if len(events) < 3:
                continue

            event_dicts = []
            for ev in events:
                event_dicts.append({
                    "id": ev[0],
                    "title": ev[1],
                    "severity": ev[2],
                    "confidence": ev[3],
                    "event_time": ev[4],
                    "source_tier": ev[5],
                    "country_code": ev[6],
                    "geohash5": ev[7],
                    "lat": ev[8],
                    "lon": ev[9],
                    "image_url": ev[10],
                    "body": ev[11],
                    "topic": ev[12],
                    "entity_anchor": ev[13],
                    "title_ko": None,
                })

            groups = _group_events_by_similarity(event_dicts)

            if len(groups) <= 1:
                continue

            # 분리 필요!
            total_splits += 1
            group_sizes = [len(g) for g in groups]
            print(f"\n{'='*70}")
            print(f"분리: {cl_key} | {(cl_title_ko or cl_title)[:50]}")
            print(f"  원본: {cl_event_count}개 → {len(groups)}개 그룹 {group_sizes}")

            for gi, group in enumerate(groups):
                rep_title = group[0]["title"][:60]
                print(f"  그룹 {gi+1} ({len(group)}개): {rep_title}")

            if DRY_RUN:
                total_new_clusters += len(groups) - 1
                continue

            # 각 그룹 내 junk 이벤트 제목을 그룹 대표 제목으로 교체
            junk_fixed = 0
            for group in groups:
                # 그룹에서 가장 좋은 제목 찾기 (non-junk, severity 높은 것)
                non_junk = [e for e in group if not _is_junk_title(e["title"])]
                if not non_junk:
                    continue
                best_title = max(non_junk, key=lambda e: e["severity"])["title"]
                for ev in group:
                    if _is_junk_title(ev["title"]):
                        await db.execute(text("""
                            UPDATE normalized_events SET title = :title WHERE id = :eid
                        """), {"title": best_title, "eid": str(ev["id"])})
                        ev["title"] = best_title
                        junk_fixed += 1
            if junk_fixed:
                print(f"  → junk 이벤트 제목 {junk_fixed}개 교체")

            # 가장 큰 그룹이 원본 클러스터를 유지
            groups.sort(key=len, reverse=True)

            for gi, group in enumerate(groups):
                if gi == 0:
                    # 가장 큰 그룹 → 원본 클러스터 업데이트
                    first_ev = min(group, key=lambda e: e["event_time"])
                    last_ev = max(group, key=lambda e: e["event_time"])
                    max_sev = max(e["severity"] for e in group)
                    avg_conf = sum(e["confidence"] for e in group) / len(group)
                    tiers = [e["source_tier"] for e in group if e["source_tier"]]

                    # 대표 제목 결정
                    best_title_ev = max(group, key=lambda e: e["severity"])
                    new_title = best_title_ev["title"]
                    new_title_ko = _make_cluster_title_ko(new_title, cl_topic, cl_country)

                    # AI 제목 생성 시도
                    top_events = sorted(group, key=lambda e: e["severity"], reverse=True)[:3]
                    ai = generate_ai_title(
                        [{"title": e["title"], "body": e.get("body") or ""} for e in top_events],
                        cl_topic, cl_country,
                    )
                    if ai:
                        new_title, new_title_ko = ai

                    # kscore 계산
                    now = datetime.now(timezone.utc)
                    age_hours = (now - last_ev["event_time"]).total_seconds() / 3600
                    new_kscore, _ = _calc_kscore(
                        event_count=len(group),
                        is_spike=False,
                        confidence=round(avg_conf, 3),
                        severity=max_sev,
                        independent_sources=len(set(tiers)),
                        source_tiers=tiers,
                        age_hours=age_hours,
                    )

                    # 원본 클러스터에서 분리된 이벤트 제거
                    split_event_ids = []
                    for other_group in groups[1:]:
                        split_event_ids.extend(str(e["id"]) for e in other_group)

                    if split_event_ids:
                        # asyncpg는 IN절에 리스트를 직접 바인딩 못하므로 개별 삭제
                        for eid in split_event_ids:
                            await db.execute(text(
                                "DELETE FROM cluster_events WHERE cluster_id = :cid AND event_id = :eid"
                            ), {"cid": str(cl_id), "eid": eid})

                    # 원본 클러스터 메타 업데이트
                    img = next((e["image_url"] for e in group if e.get("image_url")), cl_image_url)
                    await db.execute(text("""
                        UPDATE issue_clusters SET
                            title = :title, title_ko = :title_ko,
                            event_count = :cnt, severity = :sev,
                            confidence = :conf, kscore = :kscore,
                            source_tiers = :tiers,
                            first_event_at = :first_at, last_event_at = :last_at,
                            window_end = :wend, image_url = :img,
                            updated_at = NOW()
                        WHERE id = :cid
                    """), {
                        "cid": str(cl_id),
                        "title": new_title,
                        "title_ko": new_title_ko,
                        "cnt": len(group),
                        "sev": max_sev,
                        "conf": round(avg_conf, 3),
                        "kscore": round(new_kscore, 3),
                        "tiers": tiers,
                        "first_at": first_ev["event_time"],
                        "last_at": last_ev["event_time"],
                        "wend": last_ev["event_time"] + timedelta(minutes=60),
                        "img": img,
                    })
                    print(f"  → 원본 유지 ({len(group)}개): {(new_title_ko or new_title)[:50]}")

                else:
                    # 새 클러스터 생성
                    first_ev = min(group, key=lambda e: e["event_time"])
                    last_ev = max(group, key=lambda e: e["event_time"])
                    max_sev = max(e["severity"] for e in group)
                    avg_conf = sum(e["confidence"] for e in group) / len(group)
                    tiers = [e["source_tier"] for e in group if e["source_tier"]]

                    best_title_ev = max(group, key=lambda e: e["severity"])
                    new_title = best_title_ev["title"]
                    new_title_ko = _make_cluster_title_ko(new_title, cl_topic, cl_country)

                    ai = generate_ai_title(
                        [{"title": e["title"], "body": e.get("body") or ""} for e in
                         sorted(group, key=lambda e: e["severity"], reverse=True)[:3]],
                        cl_topic, cl_country,
                    )
                    if ai:
                        new_title, new_title_ko = ai

                    now = datetime.now(timezone.utc)
                    age_hours = (now - last_ev["event_time"]).total_seconds() / 3600
                    new_kscore, _ = _calc_kscore(
                        event_count=len(group),
                        is_spike=False,
                        confidence=round(avg_conf, 3),
                        severity=max_sev,
                        independent_sources=len(set(tiers)),
                        source_tiers=tiers,
                        age_hours=age_hours,
                    )

                    img = next((e["image_url"] for e in group if e.get("image_url")), None)
                    geo5 = next((e["geohash5"] for e in group if e.get("geohash5")), cl_geohash5) or "00000"
                    lat = next((e["lat"] for e in group if e.get("lat")), cl_lat)
                    lon = next((e["lon"] for e in group if e.get("lon")), cl_lon)
                    cc = next((e["country_code"] for e in group if e.get("country_code")), cl_country)
                    anchor = next((e["entity_anchor"] for e in group if e.get("entity_anchor")), cl_entity_anchor)

                    new_id = str(uuid.uuid4())

                    await db.execute(text("""
                        INSERT INTO issue_clusters (
                            id, cluster_key, geohash5, topic, entity_anchor,
                            country_code, lat, lon, title, title_ko,
                            event_count, severity, confidence, kscore,
                            is_spike, source_tiers, independent_sources,
                            first_event_at, last_event_at,
                            window_start, window_end,
                            image_url, is_verified, created_at, updated_at
                        ) VALUES (
                            :id, :key, :geo5, :topic, :anchor,
                            :cc, :lat, :lon, :title, :title_ko,
                            :cnt, :sev, :conf, :kscore,
                            false, :tiers, :isrc,
                            :first_at, :last_at,
                            :wstart, :wend,
                            :img, false, NOW(), NOW()
                        )
                    """), {
                        "id": new_id,
                        "key": cl_key,
                        "geo5": geo5,
                        "topic": cl_topic,
                        "anchor": anchor,
                        "cc": cc,
                        "lat": lat,
                        "lon": lon,
                        "title": new_title,
                        "title_ko": new_title_ko,
                        "cnt": len(group),
                        "sev": max_sev,
                        "conf": round(avg_conf, 3),
                        "kscore": round(new_kscore, 3),
                        "tiers": tiers,
                        "isrc": len(set(tiers)),
                        "first_at": first_ev["event_time"],
                        "last_at": last_ev["event_time"],
                        "wstart": first_ev["event_time"] - timedelta(minutes=60),
                        "wend": last_ev["event_time"] + timedelta(minutes=60),
                        "img": img,
                    })

                    # cluster_events 이동
                    for ev in group:
                        await db.execute(text(
                            "UPDATE cluster_events SET cluster_id = :new_cid "
                            "WHERE cluster_id = :old_cid AND event_id = :eid"
                        ), {"new_cid": new_id, "old_cid": str(cl_id), "eid": str(ev["id"])})

                    total_new_clusters += 1
                    print(f"  → 새 클러스터 ({len(group)}개): {(new_title_ko or new_title)[:50]}")

        if not DRY_RUN:
            await db.commit()
            print(f"\n{'='*70}")
            print(f"완료: {total_splits}개 클러스터 분리, {total_new_clusters}개 새 클러스터 생성")
        else:
            print(f"\n{'='*70}")
            print(f"[DRY-RUN] {total_splits}개 클러스터 분리 예정, {total_new_clusters}개 새 클러스터 생성 예정")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(recluster())
