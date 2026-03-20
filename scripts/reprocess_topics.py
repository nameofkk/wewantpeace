"""
기존 normalized_events의 topic/country_code/severity/geo를 소급 재처리.

사용 시점:
  normalizer.py의 COUNTRY_MAP, TOPIC_KEYWORDS, severity 설정이 변경되면
  반드시 이 스크립트를 실행해 기존 DB 데이터에 반영한다.

처리 순서:
  1. normalized_events 재분류 (topic / country_code / lat/lon / severity)
  2. issue_clusters geo 동기화 (country_code / lat / lon / geohash5)
  3. issue_clusters topic/severity 동기화 (이벤트 최대 severity 반영)
  4. 카니발·축제 등 노이즈 클러스터 비활성화
     (severity < 20 AND topic = 'unknown' → 검색에서 제외되도록 severity=0으로 설정)

실행:
  python3 scripts/reprocess_topics.py           # 변경된 것만 처리
  python3 scripts/reprocess_topics.py --all     # 전체 강제 재처리
"""
import asyncio
import sys

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal
from worker.processor.normalizer import (
    _classify_topic, _classify_sub_topic, _extract_geo, _make_geohash,
    _calculate_severity, is_relevant, NormalizeResult,
)

FORCE_ALL = "--all" in sys.argv


async def step1_reprocess_events(db):
    """normalized_events 재분류 (sub_topic 포함)."""
    if FORCE_ALL:
        r = await db.execute(text("""
            SELECT id, topic, country_code, body, title, source_tier, severity,
                   COALESCE(sub_topic, 'general') as sub_topic
            FROM normalized_events
            ORDER BY id
        """))
    else:
        r = await db.execute(text("""
            SELECT id, topic, country_code, body, title, source_tier, severity,
                   COALESCE(sub_topic, 'general') as sub_topic
            FROM normalized_events
            WHERE topic = 'unknown' OR country_code IS NULL OR sub_topic = 'general'
            ORDER BY id
        """))
    rows = r.fetchall()

    print(f"[Step 1] 재처리 대상: {len(rows)}개 이벤트 (--all={FORCE_ALL})")

    changed = skipped = 0
    for row in rows:
        combined = ((row.title or "") + " " + (row.body or "")).strip()
        if not combined:
            skipped += 1
            continue

        new_topic = _classify_topic(combined)
        new_country, new_lat, new_lon = _extract_geo(combined)
        new_geohash = _make_geohash(new_lat, new_lon)
        new_severity = _calculate_severity(combined, new_topic)
        new_sub_topic = _classify_sub_topic(combined, new_topic)

        if (not FORCE_ALL
                and new_topic == row.topic
                and new_country == row.country_code
                and new_severity == row.severity
                and new_sub_topic == row.sub_topic):
            skipped += 1
            continue

        print(f"  [{row.topic}→{new_topic}] [{row.sub_topic}→{new_sub_topic}] [{row.country_code}→{new_country}] sev={new_severity} | {(row.title or '')[:50]}")

        await db.execute(text("""
            UPDATE normalized_events
            SET topic = :topic,
                sub_topic = :sub_topic,
                country_code = :cc,
                lat = :lat,
                lon = :lon,
                geohash5 = :gh,
                severity = :sev
            WHERE id = :id
        """), {
            "topic": new_topic,
            "sub_topic": new_sub_topic,
            "cc": new_country,
            "lat": new_lat,
            "lon": new_lon,
            "gh": new_geohash,
            "sev": new_severity,
            "id": row.id,
        })
        changed += 1

        if changed % 20 == 0:
            await db.commit()
            print(f"  ...{changed}개 커밋")

    await db.commit()
    print(f"  완료: 변경 {changed}개 / 스킵 {skipped}개\n")
    return changed


async def step2_sync_cluster_geo(db):
    """
    issue_clusters: 연결 이벤트의 다수 country_code로 geo 재동기화.
    - 기존에 NULL인 것만 채우는 것이 아니라,
      이벤트들의 다수결 country_code와 클러스터의 country_code가 다르면 교정.
    - 이렇게 하면 "한국 기사가 영국 클러스터에 잘못 묶인" 경우도 수정됨.
    """
    print("[Step 2] 클러스터 geo 동기화 (다수결 country_code 기반)")

    # 각 클러스터에서 이벤트 country_code 다수결 + 해당 국가 대표 좌표 선택
    result = await db.execute(text("""
        UPDATE issue_clusters c
        SET
            country_code = maj.majority_cc,
            lat          = maj.lat,
            lon          = maj.lon
        FROM (
            SELECT DISTINCT ON (ce.cluster_id)
                ce.cluster_id,
                ne.country_code  AS majority_cc,
                ne.lat,
                ne.lon,
                COUNT(*) OVER (PARTITION BY ce.cluster_id, ne.country_code) AS cc_count
            FROM cluster_events ce
            JOIN normalized_events ne ON ne.id = ce.event_id
            WHERE ne.country_code IS NOT NULL
              AND ne.lat IS NOT NULL
            ORDER BY
                ce.cluster_id,
                COUNT(*) OVER (PARTITION BY ce.cluster_id, ne.country_code) DESC,
                ne.severity DESC
        ) maj
        WHERE c.id = maj.cluster_id
          AND (c.country_code IS DISTINCT FROM maj.majority_cc
               OR c.lat IS NULL)
        RETURNING c.id
    """))
    updated = len(result.fetchall())
    await db.commit()
    print(f"  geo 동기화: {updated}개 클러스터\n")


async def step2b_sync_cluster_topic(db):
    """
    issue_clusters: 연결 이벤트 중 다수결 topic으로 업데이트.
    재분류로 이벤트 topic이 바뀐 경우 클러스터 topic도 교정.
    unknown보다 구체적인 topic이 다수이면 교체.
    """
    print("[Step 2b] 클러스터 topic 동기화 (다수결)")
    result = await db.execute(text("""
        UPDATE issue_clusters c
        SET topic = maj.majority_topic
        FROM (
            SELECT DISTINCT ON (ce.cluster_id)
                ce.cluster_id,
                ne.topic AS majority_topic,
                COUNT(*) OVER (PARTITION BY ce.cluster_id, ne.topic) AS topic_count
            FROM cluster_events ce
            JOIN normalized_events ne ON ne.id = ce.event_id
            WHERE ne.topic != 'unknown'
            ORDER BY
                ce.cluster_id,
                COUNT(*) OVER (PARTITION BY ce.cluster_id, ne.topic) DESC
        ) maj
        WHERE c.id = maj.cluster_id
          AND c.topic IS DISTINCT FROM maj.majority_topic
        RETURNING c.id
    """))
    updated = len(result.fetchall())
    await db.commit()
    print(f"  topic 동기화: {updated}개 클러스터\n")


async def step3_sync_cluster_severity(db):
    """issue_clusters: 연결 이벤트의 최대 severity로 업데이트."""
    print("[Step 3] 클러스터 severity 동기화")
    result = await db.execute(text("""
        UPDATE issue_clusters c
        SET severity = sub.max_sev
        FROM (
            SELECT ce.cluster_id, MAX(ne.severity) AS max_sev
            FROM cluster_events ce
            JOIN normalized_events ne ON ne.id = ce.event_id
            GROUP BY ce.cluster_id
        ) sub
        WHERE c.id = sub.cluster_id
          AND c.severity != sub.max_sev
        RETURNING c.id
    """))
    updated = len(result.fetchall())
    await db.commit()
    print(f"  severity 동기화: {updated}개 클러스터\n")


async def step3b_fix_empty_clusters(db):
    """
    cluster_events가 0개인 클러스터 탐지 및 event_count 교정.
    이전 Step 4 버그로 고아가 된 클러스터를 찾아 event_count=0으로 표시.
    (severity=0 처리는 Step 5에서 담당)
    """
    print("[Step 3b] 빈 클러스터(actual_events=0) 탐지 및 event_count 교정")
    result = await db.execute(text("""
        UPDATE issue_clusters c
        SET event_count = 0
        WHERE c.event_count > 0
          AND NOT EXISTS (
              SELECT 1 FROM cluster_events ce WHERE ce.cluster_id = c.id
          )
        RETURNING c.id, c.title_ko
    """))
    rows = result.fetchall()
    for row in rows:
        print(f"  event_count=0 교정: {(row.title_ko or '')[:60]}")
    await db.commit()
    print(f"  교정된 클러스터: {len(rows)}개\n")


async def step4_remove_noise_events_from_clusters(db):
    """
    클러스터에서 노이즈 이벤트 제거.
    재분류 결과 topic='unknown' AND severity <= 25가 된 이벤트는
    실제 이슈 클러스터에 섞여있으면 타임라인을 오염시키므로 cluster_events에서 제거.
    """
    print("[Step 4] 클러스터에서 노이즈 이벤트 제거")

    # 삭제 대상 이벤트 확인
    r = await db.execute(text("""
        SELECT ce.cluster_id, ne.id as ne_id, ne.title, c.title as cluster_title
        FROM cluster_events ce
        JOIN normalized_events ne ON ne.id = ce.event_id
        JOIN issue_clusters c ON c.id = ce.cluster_id
        WHERE ne.topic = 'unknown' AND ne.severity <= 25
    """))
    targets = r.fetchall()

    if targets:
        for t in targets:
            print(f"  제거: [{t.title[:50]}] from [{t.cluster_title[:50]}]")

    result = await db.execute(text("""
        DELETE FROM cluster_events ce
        USING normalized_events ne
        WHERE ce.event_id = ne.id
          AND ne.topic = 'unknown'
          AND ne.severity <= 25
          -- 클러스터에 다른 이벤트가 있을 때만 제거 (마지막 이벤트 보호)
          AND (
              SELECT COUNT(*) FROM cluster_events ce2
              WHERE ce2.cluster_id = ce.cluster_id
          ) > 1
        RETURNING ce.cluster_id
    """))
    removed = len(result.fetchall())

    # 클러스터 event_count 재계산
    await db.execute(text("""
        UPDATE issue_clusters c
        SET event_count = sub.cnt
        FROM (
            SELECT cluster_id, COUNT(*) AS cnt
            FROM cluster_events
            GROUP BY cluster_id
        ) sub
        WHERE c.id = sub.cluster_id
          AND c.event_count != sub.cnt
    """))

    await db.commit()
    print(f"  제거된 cluster_event: {removed}개\n")


async def step5_deactivate_noise_clusters(db):
    """
    노이즈 클러스터 비활성화.
    event_count=0이거나 severity < 20 AND topic='unknown' → severity=0으로 설정해 지도/홈에서 제외.
    """
    print("[Step 5] 노이즈 클러스터 비활성화")
    result = await db.execute(text("""
        UPDATE issue_clusters
        SET severity = 0
        WHERE (topic = 'unknown' AND severity < 20)
           OR event_count = 0
        RETURNING id
    """))
    deactivated = len(result.fetchall())
    await db.commit()
    print(f"  비활성화: {deactivated}개 클러스터\n")


async def step6_refresh_cluster_title_prefix(db):
    """
    클러스터 title_ko의 [국가] 접두사를 현재 country_code·topic 기준으로 재생성.

    title_ko 형식: "[국가] 토픽 · 번역된 제목"
    country_code나 topic이 재처리로 바뀌어도 title_ko는 고정된 채 남아있으므로
    접두사 부분만 다시 계산해 교체한다 (번역 API 재호출 없음).

    주의: AI가 생성한 깔끔한 제목(" · " 구분자 없음)은 건드리지 않는다.
    """
    from worker.processor.clusterer import _COUNTRY_NAMES_KO, _TOPIC_LABELS_KO

    print("[Step 6] 클러스터 title_ko 접두사 재생성 (AI 제목 보존)")

    r = await db.execute(text("""
        SELECT id, title_ko, topic, country_code
        FROM issue_clusters
        WHERE title_ko IS NOT NULL
          AND title_ko LIKE '%·%'
    """))
    clusters = r.fetchall()

    updated = 0
    for c in clusters:
        old = c.title_ko or ""

        # " · " 뒤의 번역 본문 추출 — 없으면 AI 제목이므로 스킵
        if " · " not in old:
            continue
        translated = old.split(" · ", 1)[1]

        # 새 접두사 계산
        topic_label = _TOPIC_LABELS_KO.get(c.topic or "", "이슈")
        country_name = _COUNTRY_NAMES_KO.get(c.country_code or "", "") if c.country_code else ""
        new_prefix = f"[{country_name}] {topic_label}" if country_name else topic_label

        new_title = f"{new_prefix} · {translated}" if translated else new_prefix
        if len(new_title) > 70:
            new_title = new_title[:68] + "…"

        if new_title != old:
            print(f"  [{old[:45]}]")
            print(f"  → [{new_title[:45]}]")
            await db.execute(
                text("UPDATE issue_clusters SET title_ko = :t WHERE id = :id"),
                {"t": new_title, "id": c.id},
            )
            updated += 1

    await db.commit()
    print(f"  title_ko 수정: {updated}개\n")


async def step7_unlink_mismatched_cluster_events(db):
    """
    재분류 후 이벤트의 {country_code}:{topic}과 클러스터의 {country_code}:{topic}이
    불일치하는 cluster_events 링크를 제거.

    제거된 이벤트는 다음 클러스터링 사이클에서 올바른 클러스터로 재배치됨.
    마지막 이벤트 보호: 클러스터에 이벤트가 1개만 남으면 제거하지 않음.
    """
    print("[Step 7] 불일치 cluster_events 링크 제거 (이벤트 country:topic ≠ 클러스터 country:topic)")

    # 불일치 링크 확인 (디버그 출력)
    r = await db.execute(text("""
        SELECT ce.cluster_id, ce.event_id,
               ne.country_code AS ev_cc, ne.topic AS ev_topic,
               c.country_code AS cl_cc, c.topic AS cl_topic,
               ne.title
        FROM cluster_events ce
        JOIN normalized_events ne ON ne.id = ce.event_id
        JOIN issue_clusters c ON c.id = ce.cluster_id
        WHERE (COALESCE(ne.country_code, '') || ':' || ne.topic)
           != (COALESCE(c.country_code, '') || ':' || c.topic)
    """))
    targets = r.fetchall()

    if targets:
        for t in targets:
            print(f"  불일치: ev[{t.ev_cc}:{t.ev_topic}] ≠ cl[{t.cl_cc}:{t.cl_topic}] | {(t.title or '')[:50]}")

    # 불일치 링크 삭제 (마지막 이벤트 보호)
    result = await db.execute(text("""
        DELETE FROM cluster_events ce
        USING normalized_events ne, issue_clusters c
        WHERE ce.event_id = ne.id
          AND ce.cluster_id = c.id
          AND (COALESCE(ne.country_code, '') || ':' || ne.topic)
           != (COALESCE(c.country_code, '') || ':' || c.topic)
          AND (
              SELECT COUNT(*) FROM cluster_events ce2
              WHERE ce2.cluster_id = ce.cluster_id
          ) > 1
        RETURNING ce.cluster_id
    """))
    removed_rows = result.fetchall()
    removed = len(removed_rows)

    # 영향받은 클러스터의 event_count 재계산
    if removed > 0:
        await db.execute(text("""
            UPDATE issue_clusters c
            SET event_count = sub.cnt
            FROM (
                SELECT cluster_id, COUNT(*) AS cnt
                FROM cluster_events
                GROUP BY cluster_id
            ) sub
            WHERE c.id = sub.cluster_id
              AND c.event_count != sub.cnt
        """))

    await db.commit()
    print(f"  제거된 불일치 링크: {removed}개\n")


async def step8_split_oversized(db):
    """대형 클러스터를 sub_topic 기반으로 분할."""
    from worker.processor.clusterer import split_oversized_clusters

    print("[Step 8] 대형 클러스터 sub_topic 기반 분할")
    splits = await split_oversized_clusters(db)
    await db.commit()
    print(f"  분할: {len(splits)}개 새 클러스터 생성\n")


async def main():
    async with AsyncSessionLocal() as db:
        changed = await step1_reprocess_events(db)

    async with AsyncSessionLocal() as db:
        await step2_sync_cluster_geo(db)

    async with AsyncSessionLocal() as db:
        await step2b_sync_cluster_topic(db)

    async with AsyncSessionLocal() as db:
        await step3_sync_cluster_severity(db)

    async with AsyncSessionLocal() as db:
        await step3b_fix_empty_clusters(db)

    async with AsyncSessionLocal() as db:
        await step4_remove_noise_events_from_clusters(db)

    async with AsyncSessionLocal() as db:
        await step5_deactivate_noise_clusters(db)

    async with AsyncSessionLocal() as db:
        await step6_refresh_cluster_title_prefix(db)

    async with AsyncSessionLocal() as db:
        await step7_unlink_mismatched_cluster_events(db)

    # Step 8: 대형 클러스터 sub_topic 기반 분할
    async with AsyncSessionLocal() as db:
        await step8_split_oversized(db)

    print("=== 전체 재처리 완료 ===")
    print("  홈 / 지도 / 긴장도 탭에 자동 반영됩니다 (staleTime 만료 또는 새로고침 시).")


if __name__ == "__main__":
    asyncio.run(main())
