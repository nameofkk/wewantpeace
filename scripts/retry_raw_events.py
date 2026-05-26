#!/usr/bin/env python3
"""
미처리 raw_events를 로컬에서 직접 처리하는 스크립트.
Celery/Redis 없이 프로덕션 DB에 직접 연결하여 process_raw_event 로직 실행.

사용법:
  DATABASE_URL="postgresql+asyncpg://..." OPENAI_API_KEY="sk-..." \
    python3 scripts/retry_raw_events.py [--limit 200] [--dry-run]
"""
import asyncio
import argparse
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def process_one(db: AsyncSession, raw_event_id: str):
    """process_raw_event 핵심 로직 (Redis 락 없이, 별도 세션)."""
    from backend.app.models.raw_event import RawEvent
    from backend.app.models.normalized_event import NormalizedEvent
    from backend.app.models.source_channel import SourceChannel
    from worker.processor.normalizer import normalize, is_relevant
    from worker.processor.deduplicator import check_duplicate
    from worker.processor.clusterer import assign_cluster

    result = await db.execute(
        select(RawEvent).where(RawEvent.id == uuid.UUID(raw_event_id))
    )
    raw_event = result.scalar_one_or_none()
    if not raw_event:
        return "not_found"
    if raw_event.processed:
        return "already_processed"

    # source tier
    tier = "C"
    if raw_event.source_channel_id:
        ch_res = await db.execute(
            select(SourceChannel).where(SourceChannel.id == raw_event.source_channel_id)
        )
        ch = ch_res.scalar_one_or_none()
        if ch:
            tier = ch.tier

    # RSS 제목/발행일 추출
    rss_title = None
    published_at = None
    if raw_event.raw_metadata:
        if raw_event.source_type == "rss":
            rss_title = raw_event.raw_metadata.get("title") or None
            pub_str = raw_event.raw_metadata.get("published") or raw_event.raw_metadata.get("pubDate")
            if pub_str:
                try:
                    published_at = parsedate_to_datetime(pub_str)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    try:
                        published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pass
        elif raw_event.source_type in ("telegram", "twitter"):
            date_val = raw_event.raw_metadata.get("date")
            if date_val and isinstance(date_val, (int, float)):
                published_at = datetime.fromtimestamp(date_val, tz=timezone.utc)
            elif date_val and isinstance(date_val, str):
                try:
                    published_at = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                except Exception:
                    pass
        elif raw_event.source_type == "api":
            rss_title = raw_event.raw_metadata.get("title") or None
            pub_str = raw_event.raw_metadata.get("published")
            if pub_str:
                try:
                    published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pass

    image_url = (raw_event.raw_metadata or {}).get("image_url") if raw_event.raw_metadata else None

    # 구조화 데이터 (GDELT/ACLED)
    structured_meta = raw_event.raw_metadata or {}
    if (raw_event.source_type == "api"
            and structured_meta.get("structured_topic")
            and structured_meta["structured_topic"] != "unknown"):
        from worker.processor.normalizer import (
            NormalizeResult, _make_dedup_key, _calculate_confidence,
            _make_geohash, _translate_to_korean, _extract_geo,
            COUNTRY_MAP, _classify_sub_topic,
        )
        s_topic = structured_meta["structured_topic"]
        s_severity = int(structured_meta.get("structured_severity", 50))
        s_title = (rss_title or raw_event.raw_text[:120]).strip()

        s_lat = structured_meta.get("structured_lat")
        s_lon = structured_meta.get("structured_lon")
        s_country = structured_meta.get("structured_country")
        if s_lat and s_lon and s_country:
            s_lat = float(s_lat)
            s_lon = float(s_lon)
            country_lower = s_country.lower()
            if country_lower in COUNTRY_MAP:
                s_cc = COUNTRY_MAP[country_lower][0]
            else:
                s_cc, s_lat, s_lon = _extract_geo(s_title + " " + s_country)
        else:
            s_cc, s_lat, s_lon = _extract_geo(raw_event.raw_text, title=s_title)

        s_geohash = _make_geohash(s_lat, s_lon)
        s_confidence = _calculate_confidence(tier, s_severity)
        s_dedup = _make_dedup_key(raw_event.raw_text)
        s_title_ko = _translate_to_korean(s_title)
        s_body_ko = _translate_to_korean(raw_event.raw_text[:500])
        s_sub_topic = _classify_sub_topic(
            (s_title + " " + raw_event.raw_text[:500]), s_topic,
        )
        norm = NormalizeResult(
            title=s_title[:120],
            title_ko=s_title_ko,
            body=raw_event.raw_text[:2000],
            body_ko=s_body_ko,
            topic=s_topic,
            sub_topic=s_sub_topic,
            entity_anchor=s_cc or s_title[:64],
            lat=s_lat,
            lon=s_lon,
            geohash5=s_geohash,
            country_code=s_cc,
            severity=s_severity,
            source_tier=tier,
            confidence=s_confidence,
            dedup_key=s_dedup,
            lang="en",
            translation_status="skipped",
            geo_method="structured" if s_cc else "none",
            event_time=published_at or raw_event.collected_at,
            image_url=image_url,
        )
    else:
        # GPT 기반 정규화 (동기 함수 — asyncio.to_thread 불필요)
        norm = normalize(
            raw_text=raw_event.raw_text,
            source_tier=tier,
            collected_at=raw_event.collected_at,
            source_title=rss_title,
            published_at=published_at,
            image_url=image_url,
        )

    # 관련성 필터
    if not is_relevant(norm):
        raw_event.processed = True
        return f"irrelevant(topic={norm.topic})"

    # 중복 확인
    is_dup = await check_duplicate(norm.dedup_key, db)

    # NormalizedEvent 저장
    ne = NormalizedEvent(
        raw_event_id=raw_event.id,
        title=norm.title,
        title_ko=norm.title_ko,
        body=norm.body,
        body_ko=norm.body_ko,
        topic=norm.topic,
        sub_topic=getattr(norm, "sub_topic", "general") or "general",
        entity_anchor=norm.entity_anchor,
        lat=norm.lat,
        lon=norm.lon,
        geohash5=norm.geohash5,
        country_code=norm.country_code,
        severity=norm.severity,
        source_tier=norm.source_tier,
        confidence=norm.confidence,
        dedup_key=norm.dedup_key,
        is_duplicate=is_dup,
        translation_status=norm.translation_status,
        geo_method=norm.geo_method,
        image_url=norm.image_url,
        event_time=norm.event_time,
    )
    db.add(ne)
    await db.flush()

    # 클러스터 할당 (UniqueViolation 발생 시 기존 클러스터에 추가 시도)
    cluster_id = None
    if not is_dup:
        try:
            cluster, _ = await assign_cluster(ne, db)
            if cluster is not None:
                cluster_id = str(cluster.id)
        except Exception as e:
            if "UniqueViolation" in str(type(e).__name__) or "unique" in str(e).lower():
                logger.warning("클러스터 중복 키 충돌 — 무시하고 계속: %s", e)
                # 클러스터 할당 실패해도 NormalizedEvent는 저장됨
            else:
                raise

    raw_event.processed = True
    return f"ok(topic={norm.topic}, sev={norm.severity}, dup={is_dup}, cluster={cluster_id})"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL 환경변수를 설정하세요.")
        sys.exit(1)

    engine = create_async_engine(
        db_url, pool_size=3, max_overflow=2,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
            "server_settings": {"jit": "off"},
        },
    )
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from backend.app.models.raw_event import RawEvent

    # 먼저 미처리 이벤트 ID 목록만 조회
    async with Session() as db:
        result = await db.execute(
            select(RawEvent.id)
            .where(RawEvent.processed == False)
            .order_by(RawEvent.collected_at.asc())
            .limit(args.limit)
        )
        event_ids = [str(row[0]) for row in result.fetchall()]

    logger.info("미처리 raw_events: %d건 (limit=%d)", len(event_ids), args.limit)

    if args.dry_run:
        async with Session() as db:
            result = await db.execute(
                select(RawEvent)
                .where(RawEvent.id.in_([uuid.UUID(eid) for eid in event_ids]))
            )
            for e in result.scalars().all():
                logger.info("  [DRY-RUN] ID=%s type=%s text=%s...",
                            e.id, e.source_type, (e.raw_text or "")[:60])
        await engine.dispose()
        return

    success = 0
    failed = 0
    for i, eid in enumerate(event_ids):
        # 각 이벤트를 별도 세션에서 처리 (세션 오염 방지)
        try:
            async with Session() as db:
                async with db.begin():
                    status = await process_one(db, eid)
                    logger.info("[%d/%d] ID=%s → %s", i + 1, len(event_ids), eid, status)
                    success += 1
        except Exception as exc:
            logger.error("[%d/%d] ID=%s FAILED: %s", i + 1, len(event_ids), eid, str(exc)[:200])
            failed += 1

    logger.info("완료: 성공=%d, 실패=%d, 총=%d", success, failed, len(event_ids))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
