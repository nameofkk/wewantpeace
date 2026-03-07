"""
Celery 태스크 정의.
수집 / 처리 / 계산 파이프라인.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from worker.celery_app import app
from backend.app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def run_async(coro):
    """동기 Celery 태스크에서 비동기 코드 실행 헬퍼.

    Celery fork 워커에서 매 태스크마다 새 이벤트 루프를 생성한다.
    루프를 매번 닫지 않고 스레드-로컬에 캐싱하여 재사용한다.
    이렇게 하면 asyncpg 커넥션 풀이 동일 루프에 바인딩되어
    'Event loop is closed' / 'Future attached to a different loop' 오류를 방지한다.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@app.task(
    name="worker.tasks.collect_telegram",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def collect_telegram(self):
    """Telegram 화이트리스트 채널 수집 (5분마다)."""

    async def _run():
        from worker.collector.telegram_collector import TelegramCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = TelegramCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()   # ID 생성을 위해 flush 먼저
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                for raw_id in all_ids:
                    process_raw_event.delay(raw_id)
                logger.info("Telegram 수집 완료: 총 %d개 새 이벤트 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("Telegram 수집 완료: 총 %d개 새 이벤트", total)
            return {"total_collected": total, "channels": len(results)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("Telegram 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_rss",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def collect_rss(self):
    """RSS 피드 수집 (10분마다)."""

    async def _run():
        from worker.collector.rss_collector import RSSCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = RSSCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()   # ID 생성을 위해 flush 먼저
                # 각 raw_event의 ID 수집 (flush 후 ID 할당됨)
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                # 처리 파이프라인 체이닝 (commit 후)
                for raw_id in all_ids:
                    process_raw_event.delay(raw_id)
                logger.info("RSS 수집 완료: 총 %d개 새 이벤트 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("RSS 수집 완료: 총 %d개 새 이벤트", total)
            return {"total_collected": total, "feeds": len(results)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("RSS 수집 오류: %s", exc)
        raise self.retry(exc=exc)


# ── API 소스 수집 태스크 (소스 확장 Phase 3) ──────────────────────────────────

@app.task(
    name="worker.tasks.collect_gdelt",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def collect_gdelt(self):
    """GDELT DOC API 수집 (15분마다)."""

    async def _run():
        from worker.collector.gdelt_collector import GDELTCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = GDELTCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                for raw_id in all_ids:
                    process_raw_event.delay(raw_id)
                logger.info("GDELT 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("GDELT 수집 완료: 총 %d개", total)
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("GDELT 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_acled",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def collect_acled(self):
    """ACLED API 수집 (주간 배치)."""

    async def _run():
        from worker.collector.acled_collector import ACLEDCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = ACLEDCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                for raw_id in all_ids:
                    process_raw_event.delay(raw_id)
                logger.info("ACLED 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("ACLED 수집 완료: 총 %d개", total)
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("ACLED 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_reliefweb",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def collect_reliefweb(self):
    """ReliefWeb API 수집 (30분마다)."""

    async def _run():
        from worker.collector.reliefweb_collector import ReliefWebCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = ReliefWebCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                for raw_id in all_ids:
                    process_raw_event.delay(raw_id)
                logger.info("ReliefWeb 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("ReliefWeb 수집 완료: 총 %d개", total)
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("ReliefWeb 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.process_raw_event",
    queue="process",
    bind=True,
    max_retries=3,
)
def process_raw_event(self, raw_event_id: str):
    """
    단일 RawEvent 처리 파이프라인:
    normalize → dedup check → save normalized → cluster assign → spike eval
    """
    async def _run():
        import uuid
        from sqlalchemy import select
        from backend.app.models.raw_event import RawEvent
        from backend.app.models.normalized_event import NormalizedEvent
        from backend.app.models.source_channel import SourceChannel
        from worker.processor.normalizer import normalize, is_relevant
        from worker.processor.deduplicator import check_duplicate
        from worker.processor.clusterer import assign_cluster
        from worker.processor.spike_detector import evaluate_spike
        from backend.app.core.redis import get_redis

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 1. RawEvent 조회
                result = await db.execute(
                    select(RawEvent).where(RawEvent.id == uuid.UUID(raw_event_id))
                )
                raw_event = result.scalar_one_or_none()
                if not raw_event:
                    logger.warning("RawEvent 없음: %s", raw_event_id)
                    return {"status": "not_found"}
                if raw_event.processed:
                    return {"status": "already_processed"}

                # 2. 소스 tier 조회
                tier = "C"
                if raw_event.source_channel_id:
                    ch_res = await db.execute(
                        select(SourceChannel).where(
                            SourceChannel.id == raw_event.source_channel_id
                        )
                    )
                    ch = ch_res.scalar_one_or_none()
                    if ch:
                        tier = ch.tier

                # 3. 정규화
                # RSS 이벤트는 raw_metadata["title"]을 원본 제목으로 우선 사용
                rss_title = None
                published_at = None
                if raw_event.raw_metadata:
                    if raw_event.source_type == "rss":
                        rss_title = raw_event.raw_metadata.get("title") or None
                        # RSS published 필드: RFC-2822 또는 ISO 8601 문자열
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
                                    published_at = None
                    elif raw_event.source_type in ("telegram", "twitter"):
                        # Telegram: raw_metadata["date"] = Unix timestamp (int)
                        date_val = raw_event.raw_metadata.get("date")
                        if date_val and isinstance(date_val, (int, float)):
                            published_at = datetime.fromtimestamp(date_val, tz=timezone.utc)
                        elif date_val and isinstance(date_val, str):
                            try:
                                published_at = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                            except Exception:
                                published_at = None
                    elif raw_event.source_type == "api":
                        rss_title = raw_event.raw_metadata.get("title") or None
                        pub_str = raw_event.raw_metadata.get("published")
                        if pub_str:
                            try:
                                published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                            except Exception:
                                published_at = None

                image_url = (raw_event.raw_metadata or {}).get("image_url") if raw_event.raw_metadata else None

                # API 소스의 구조화 데이터: GDELT/ACLED는 이미 topic/severity/geo가 있으므로 GPT 스킵
                structured_meta = raw_event.raw_metadata or {}
                if (raw_event.source_type == "api"
                        and structured_meta.get("structured_topic")
                        and structured_meta["structured_topic"] != "unknown"):
                    from worker.processor.normalizer import (
                        NormalizeResult, _make_dedup_key, _calculate_confidence,
                        _make_geohash, _translate_to_korean, _extract_geo,
                    )
                    s_topic = structured_meta["structured_topic"]
                    s_severity = int(structured_meta.get("structured_severity", 50))
                    s_title = (rss_title or raw_event.raw_text[:120]).strip()

                    # geo: 구조화 데이터 우선, 없으면 키워드 추출
                    s_lat = structured_meta.get("structured_lat")
                    s_lon = structured_meta.get("structured_lon")
                    s_country = structured_meta.get("structured_country")
                    if s_lat and s_lon and s_country:
                        # ACLED 구조화 geo 사용
                        from worker.processor.normalizer import COUNTRY_MAP
                        s_lat = float(s_lat)
                        s_lon = float(s_lon)
                        # 국가명 → 코드 매핑
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

                    norm = NormalizeResult(
                        title=s_title[:120],
                        title_ko=s_title_ko,
                        body=raw_event.raw_text[:2000],
                        topic=s_topic,
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
                    logger.debug("구조화 데이터 정규화: topic=%s, sev=%d, cc=%s", s_topic, s_severity, s_cc)
                else:
                    norm = await asyncio.to_thread(
                        normalize,
                        raw_text=raw_event.raw_text,
                        source_tier=tier,
                        collected_at=raw_event.collected_at,
                        source_title=rss_title,
                        published_at=published_at,
                        image_url=image_url,
                    )

                # 3-1. 관련성 필터: topic=unknown & 지리정보 없으면 버림
                if not is_relevant(norm):
                    raw_event.processed = True
                    logger.debug(
                        "관련성 없음(topic=%s, country=%s), 건너뜀: %s",
                        norm.topic, norm.country_code, raw_event_id,
                    )
                    return {"status": "irrelevant", "topic": norm.topic}

                # 4. 중복 확인
                is_dup = await check_duplicate(norm.dedup_key, db)

                # 5. NormalizedEvent 저장
                ne = NormalizedEvent(
                    raw_event_id=raw_event.id,
                    title=norm.title,
                    title_ko=norm.title_ko,
                    body=norm.body,
                    topic=norm.topic,
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

                # 6. 중복 아닌 경우 클러스터 할당 + 스파이크 평가
                cluster_id = None
                is_spike = False
                spike_event_id = None

                just_verified = False
                is_new_spike = False
                if not is_dup:
                    cluster, just_verified = await assign_cluster(ne, db)
                    if cluster is not None:
                        cluster_id = str(cluster.id)

                        # 스파이크 감지 (누적 기반) — 이미 스파이크인 클러스터는 스킵
                        if not cluster.is_spike:
                            try:
                                redis = get_redis()
                                is_spike, spike_event_id = await evaluate_spike(
                                    cluster_id=cluster_id,
                                    severity=cluster.severity,
                                    event_count=cluster.event_count,
                                    independent_sources=cluster.independent_sources or 1,
                                    first_event_at=cluster.first_event_at,
                                    kscore=cluster.kscore,
                                    redis=redis,
                                )
                                if is_spike:
                                    cluster.is_spike = True
                                    cluster.spike_at = datetime.now(timezone.utc)
                                    is_new_spike = True
                            except Exception as e:
                                logger.warning("스파이크 감지 오류 (무시): %s", e)

                # 7. 처리 완료 플래그
                raw_event.processed = True

        # 새 스파이크만 알림 태스크 체이닝 (트랜잭션 밖에서)
        if is_new_spike and cluster_id:
            push_spike_alert.delay(cluster_id, spike_event_id)

        # 공식확인 전환 시 verified 알림 태스크 체이닝
        if just_verified and cluster_id:
            push_verified_alert.delay(cluster_id)

        return {
            "status": "ok",
            "raw_event_id": raw_event_id,
            "is_duplicate": is_dup,
            "cluster_id": cluster_id,
            "topic": norm.topic,
            "severity": norm.severity,
            "is_spike": is_spike,
        }

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("process_raw_event 오류 [%s]: %s", raw_event_id, exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.calculate_tension",
    queue="process",
    bind=True,
    max_retries=2,
)
def calculate_tension(self):
    """긴장도 지수 계산 (15분마다)."""

    async def _run():
        from worker.processor.tension_calculator import calculate_all_tensions
        async with AsyncSessionLocal() as db:
            async with db.begin():
                results = await calculate_all_tensions(db)
                logger.info("긴장도 계산 완료: %d개국", len(results))
                return {"status": "ok", "countries": len(results)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("긴장도 계산 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.calculate_trending",
    queue="process",
    bind=True,
    max_retries=2,
)
def calculate_trending(self):
    """트렌딩 키워드 계산 (15분마다). 분산 클러스터 자동 병합 포함."""

    async def _merge_fragmented_clusters(db):
        """같은 cluster_key의 분산된 클러스터를 병합 (보수적).

        병합 조건:
        - 8개 토픽 (conflict/terror/coup + diplomacy/maritime/protest/sanctions/cyber)
        - cluster_key가 '0000'으로 시작하지 않을 것 (위치 미상 = 혼합 위험)
        - winner의 event_count가 100 이하일 때만
        - loser의 last_event_at이 winner 기준 72시간 이내
        - 광범위 토픽은 title_overlap >= 0.25 필요
        """
        from collections import defaultdict
        from sqlalchemy import select, text
        from backend.app.models.issue_cluster import IssueCluster
        from worker.processor.trending_engine import _calc_kscore

        _MERGE_TOPICS = {"conflict", "terror", "coup", "diplomacy", "maritime", "protest", "sanctions", "cyber"}
        _BROAD_TOPICS = {"diplomacy", "protest", "maritime", "sanctions", "cyber"}
        _MAX_EVENTS = 100
        _TIME_WINDOW = timedelta(hours=72)

        result = await db.execute(
            select(IssueCluster).where(
                IssueCluster.severity > 0,
                IssueCluster.topic.in_(_MERGE_TOPICS),
            ).order_by(
                IssueCluster.cluster_key,
                IssueCluster.kscore.desc(),
            )
        )
        clusters = result.scalars().all()

        groups: dict[str, list] = defaultdict(list)
        for c in clusters:
            if c.cluster_key and not c.cluster_key.startswith("0000"):
                groups[c.cluster_key].append(c)

        merged_total = 0
        for key, group in groups.items():
            if len(group) <= 1:
                continue
            winner = group[0]
            for loser in group[1:]:
                if winner.event_count >= _MAX_EVENTS:
                    break
                if (winner.last_event_at and loser.last_event_at
                        and abs((winner.last_event_at - loser.last_event_at).total_seconds()) > _TIME_WINDOW.total_seconds()):
                    continue
                # 광범위 토픽: 제목 유사도 체크 (다른 이슈 오병합 방지)
                topic = winner.topic or ""
                if topic in _BROAD_TOPICS:
                    from worker.processor.clusterer import _title_overlap
                    if _title_overlap(winner.title or "", loser.title or "") < 0.25:
                        continue

                # 제목 교체: winner가 쓰레기 제목이면 loser 것으로 승격
                from worker.processor.trending_engine import _is_junk_title
                if _is_junk_title(winner.title or "") and not _is_junk_title(loser.title or ""):
                    winner.title = loser.title
                    winner.title_ko = loser.title_ko

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
                    winner.window_end = loser.last_event_at + timedelta(minutes=720)
                await db.execute(
                    text("UPDATE cluster_events SET cluster_id = :w WHERE cluster_id = :l"),
                    {"w": winner.id, "l": loser.id},
                )
                loser.severity = 0
                loser.kscore = 0
                merged_total += 1

            age_hours = (datetime.now(timezone.utc) - winner.last_event_at).total_seconds() / 3600 if winner.last_event_at else 0.0
            winner.kscore = _calc_kscore(
                event_count=winner.event_count,
                is_spike=winner.is_spike,
                confidence=winner.confidence,
                severity=winner.severity,
                independent_sources=winner.independent_sources or 1,
                source_tiers=winner.source_tiers or [],
                age_hours=age_hours,
            )
            winner.updated_at = datetime.now(timezone.utc)

        if merged_total:
            logger.info("분산 클러스터 %d개 병합 완료", merged_total)
        return merged_total

    async def _run():
        from worker.processor.trending_engine import calculate_global_trending
        async with AsyncSessionLocal() as db:
            async with db.begin():
                merged = await _merge_fragmented_clusters(db)
                results = await calculate_global_trending(db)
                logger.info("트렌딩 계산 완료: %d개 (클러스터 %d개 병합)", len(results), merged)
                return {"status": "ok", "count": len(results), "merged": merged}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("트렌딩 계산 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.reprocess_orphans",
    queue="process",
    bind=True,
    max_retries=1,
)
def reprocess_orphans(self):
    """
    클러스터 미할당 이벤트(오펀) 재처리 (6시간마다).
    cluster_events에 없는 normalized_events를 찾아 assign_cluster() 재실행.
    """
    async def _run():
        from sqlalchemy import select, not_, exists
        from backend.app.models.normalized_event import NormalizedEvent
        from backend.app.models.issue_cluster import ClusterEvent
        from worker.processor.clusterer import assign_cluster
        from worker.processor.spike_detector import evaluate_spike
        from backend.app.core.redis import get_redis
        from datetime import datetime, timezone, timedelta, timedelta

        reassigned = 0
        skipped = 0
        zombie_count = 0

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # cluster_events에 없는 normalized_events (severity>=20, 7일 이내)
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                orphan_result = await db.execute(
                    select(NormalizedEvent).where(
                        NormalizedEvent.severity >= 20,
                        NormalizedEvent.event_time >= cutoff,
                        not_(
                            exists().where(
                                ClusterEvent.event_id == NormalizedEvent.id
                            )
                        ),
                    ).order_by(NormalizedEvent.event_time.asc())
                )
                orphans = orphan_result.scalars().all()
                logger.info("오펀 이벤트 %d개 발견, 재처리 시작", len(orphans))

                for ev in orphans:
                    try:
                        cluster, _ = await assign_cluster(ev, db)
                        if cluster:
                            reassigned += 1
                            # 스파이크 재평가 (누적 기반)
                            try:
                                redis = get_redis()
                                is_spike, _spike_eid = await evaluate_spike(
                                    cluster_id=str(cluster.id),
                                    severity=cluster.severity,
                                    event_count=cluster.event_count,
                                    independent_sources=cluster.independent_sources or 1,
                                    first_event_at=cluster.first_event_at,
                                    kscore=cluster.kscore,
                                    redis=redis,
                                )
                                if is_spike and not cluster.is_spike:
                                    cluster.is_spike = True
                                    cluster.spike_at = datetime.now(timezone.utc)
                            except Exception:
                                pass
                        else:
                            skipped += 1
                    except Exception as e:
                        logger.warning("오펀 재처리 실패 [%s]: %s", ev.id, e)
                        skipped += 1

        logger.info("오펀 재처리 완료: reassigned=%d, skipped=%d", reassigned, skipped)

        # 좀비 클러스터 정리 (cluster_events 없는 클러스터)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from sqlalchemy import text
                result = await db.execute(text("""
                    DELETE FROM issue_clusters
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cluster_events ce WHERE ce.cluster_id = issue_clusters.id
                    )
                    RETURNING id
                """))
                zombie_count = len(result.fetchall())
                if zombie_count:
                    logger.info("좀비 클러스터 %d개 정리", zombie_count)

        # 트렌딩 갱신 트리거
        if reassigned > 0:
            calculate_trending.delay()

        return {"status": "ok", "reassigned": reassigned, "skipped": skipped, "zombies_cleaned": zombie_count}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("reprocess_orphans 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.push_spike_alert",
    queue="process",
    bind=True,
    max_retries=2,
)
def push_spike_alert(self, cluster_id: str, spike_event_id: str | None = None):
    """스파이크 알림 발송."""

    async def _run():
        import uuid
        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster
        from worker.push.push_service import send_spike_alert
        from backend.app.core.redis import get_redis

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(IssueCluster).where(IssueCluster.id == uuid.UUID(cluster_id))
                )
                cluster = result.scalar_one_or_none()
                if not cluster:
                    logger.warning("push_spike_alert: cluster 없음 %s", cluster_id)
                    return {"status": "not_found"}

                redis = get_redis()
                result = await send_spike_alert(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title,
                    country_code=cluster.country_code,
                    severity=cluster.severity,
                    kscore=cluster.kscore,
                    is_verified=cluster.is_verified,
                    cluster_topic=cluster.topic,
                    db=db,
                    redis=redis,
                    spike_event_id=spike_event_id,
                )

                # 인앱 알림 저장
                from worker.push.push_service import save_in_app_notifications
                await save_in_app_notifications(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title_ko or cluster.title,
                    country_code=cluster.country_code,
                    notif_type="spike",
                    db=db,
                )

                logger.info("push_spike_alert 완료: %s", result)
                return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("push_spike_alert 오류 [%s]: %s", cluster_id, exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.push_verified_alert",
    queue="process",
    bind=True,
    max_retries=2,
)
def push_verified_alert(self, cluster_id: str):
    """공식확인(verified) 전환 알림 발송."""

    async def _run():
        import uuid
        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster
        from worker.push.push_service import send_verified_alert, save_in_app_notifications
        from backend.app.core.redis import get_redis

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(IssueCluster).where(IssueCluster.id == uuid.UUID(cluster_id))
                )
                cluster = result.scalar_one_or_none()
                if not cluster:
                    logger.warning("push_verified_alert: cluster 없음 %s", cluster_id)
                    return {"status": "not_found"}

                redis = get_redis()
                result = await send_verified_alert(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title_ko or cluster.title,
                    country_code=cluster.country_code,
                    severity=cluster.severity,
                    kscore=cluster.kscore,
                    cluster_topic=cluster.topic,
                    db=db,
                    redis=redis,
                )

                # 인앱 알림 저장
                await save_in_app_notifications(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title_ko or cluster.title,
                    country_code=cluster.country_code,
                    notif_type="verified",
                    db=db,
                )

                logger.info("push_verified_alert 완료: %s", result)
                return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("push_verified_alert 오류 [%s]: %s", cluster_id, exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.sync_store_subscriptions",
    queue="process",
    bind=True,
    max_retries=1,
)
def sync_store_subscriptions(self):
    """
    스토어 구독 상태 동기화 (4시간마다).
    Webhook 누락 대비: Google/Apple API로 직접 구독 상태를 재확인.
    """
    async def _run():
        from sqlalchemy import select
        from backend.app.models.subscription import Subscription
        from backend.app.models.user import User

        now = datetime.now(timezone.utc)
        synced = 0
        errors = 0

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 활성/유예 상태의 스토어 구독 조회
                result = await db.execute(
                    select(Subscription).where(
                        Subscription.platform.in_(["android", "ios"]),
                        Subscription.status.in_(["active", "grace_period", "billing_retry"]),
                    )
                )
                subs = result.scalars().all()
                logger.info("sync_store_subscriptions: %d개 스토어 구독 동기화 시작", len(subs))

                for sub in subs:
                    try:
                        if sub.platform == "android" and sub.store_original_transaction_id:
                            from backend.app.services.google_play_billing import verify_subscription
                            verify_result = await verify_subscription(
                                "com.wewantpeace.app",
                                sub.store_original_transaction_id,
                            )
                            if verify_result.get("valid"):
                                # 만료 시간 업데이트
                                expiry = verify_result.get("expiry_time", "")
                                if expiry:
                                    try:
                                        sub.expires_at = datetime.fromisoformat(
                                            expiry.replace("Z", "+00:00")
                                        )
                                    except (ValueError, AttributeError):
                                        pass
                                sub.auto_renewing = verify_result.get("auto_renewing", False)
                                state = verify_result.get("state", "")
                                if state == "SUBSCRIPTION_STATE_EXPIRED":
                                    sub.status = "expired"
                                    sub.auto_renewing = False
                                elif state == "SUBSCRIPTION_STATE_IN_GRACE_PERIOD":
                                    sub.status = "grace_period"
                                elif state == "SUBSCRIPTION_STATE_ON_HOLD":
                                    sub.status = "billing_retry"
                                else:
                                    sub.status = "active"
                            else:
                                # 검증 실패 → 만료 처리
                                sub.status = "expired"
                                sub.auto_renewing = False

                        elif sub.platform == "ios" and sub.store_original_transaction_id:
                            from backend.app.services.apple_storekit import get_subscription_statuses
                            status_result = await get_subscription_statuses(
                                sub.store_original_transaction_id,
                            )
                            if status_result.get("valid"):
                                raw = status_result.get("raw", {})
                                # 구독 그룹에서 상태 추출
                                sub_groups = raw.get("data", [])
                                if sub_groups:
                                    last_txn = sub_groups[0].get("lastTransactions", [])
                                    if last_txn:
                                        status_val = last_txn[0].get("status", 0)
                                        if status_val == 1:  # Active
                                            sub.status = "active"
                                        elif status_val == 2:  # Expired
                                            sub.status = "expired"
                                            sub.auto_renewing = False
                                        elif status_val == 3:  # Billing retry
                                            sub.status = "billing_retry"
                                        elif status_val == 4:  # Grace period
                                            sub.status = "grace_period"
                                        elif status_val == 5:  # Revoked
                                            sub.status = "expired"
                                            sub.auto_renewing = False

                        sub.updated_at = now
                        synced += 1

                        # 만료된 구독의 사용자 플랜 다운그레이드
                        if sub.status in ("expired",) and (not sub.expires_at or sub.expires_at <= now):
                            user_result = await db.execute(
                                select(User).where(User.id == sub.user_id)
                            )
                            user = user_result.scalar_one_or_none()
                            if user and user.plan != "free":
                                user.plan = "free"
                                from backend.app.services.area_activation import sync_area_activation
                                await sync_area_activation(user.id, "free", db)

                    except Exception as e:
                        logger.warning("sync_store_subscriptions 오류 [%s]: %s", sub.id, e)
                        errors += 1

        logger.info("sync_store_subscriptions 완료: synced=%d, errors=%d", synced, errors)
        return {"status": "ok", "synced": synced, "errors": errors}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("sync_store_subscriptions 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.expire_subscriptions",
    queue="process",
    bind=True,
    max_retries=1,
)
def expire_subscriptions(self):
    """
    만료된 구독의 사용자 플랜을 free로 다운그레이드.
    매일 새벽 2시 UTC 실행.

    active 구독이 없거나 expires_at이 현재보다 과거인 유료 플랜 사용자를 free로 전환.
    """
    async def _run():
        from sqlalchemy import select
        from backend.app.models.user import User
        from backend.app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 유료 플랜 사용자 전체 조회
                result = await db.execute(
                    select(User).where(User.plan != "free")
                )
                users = result.scalars().all()

                downgraded = 0
                for user in users:
                    # 구독 레코드가 아예 없으면 어드민이 수동 부여한 플랜 → 건드리지 않음
                    any_sub_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                        ).limit(1)
                    )
                    if any_sub_result.scalar_one_or_none() is None:
                        continue

                    # 아직 유효한(expires_at > now) 활성 구독이 있는지 확인
                    sub_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                            Subscription.status == "active",
                            Subscription.expires_at > now,
                        ).limit(1)
                    )
                    valid_sub = sub_result.scalar_one_or_none()
                    if valid_sub is None:
                        # trial 활성 구독이 있는지도 확인
                        trial_result = await db.execute(
                            select(Subscription).where(
                                Subscription.user_id == user.id,
                                Subscription.status == "trial",
                                Subscription.trial_end.isnot(None),
                                Subscription.trial_end > now,
                            ).limit(1)
                        )
                        valid_trial = trial_result.scalar_one_or_none()
                        if valid_trial is None:
                            user.plan = "free"
                            from backend.app.services.area_activation import sync_area_activation
                            await sync_area_activation(user.id, "free", db)
                            downgraded += 1

                # Trial 만료 처리: status='trial' AND trial_end <= now
                trial_expired_result = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "trial",
                        Subscription.trial_end.isnot(None),
                        Subscription.trial_end <= now,
                    )
                )
                trial_expired = 0
                for sub in trial_expired_result.scalars().all():
                    sub.status = "expired"
                    user_result = await db.execute(
                        select(User).where(User.id == sub.user_id)
                    )
                    trial_user = user_result.scalar_one_or_none()
                    if trial_user and trial_user.plan != "free":
                        trial_user.plan = "free"
                        from backend.app.services.area_activation import sync_area_activation
                        await sync_area_activation(trial_user.id, "free", db)
                        trial_expired += 1

                logger.info("expire_subscriptions: %d명 → free 다운그레이드, trial 만료 %d명", downgraded, trial_expired)
                return {"status": "ok", "downgraded": downgraded, "trial_expired": trial_expired}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("expire_subscriptions 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 만료 FCM 토큰 주기적 정리 ──────────────────────────────────────────────

@app.task(
    bind=True,
    name="worker.tasks.cleanup_stale_tokens",
    queue="process",
    max_retries=1,
)
def cleanup_stale_tokens(self):
    """
    7일 이상 오래된 FCM 토큰 정리.
    매일 새벽 3시 UTC 실행.
    """
    async def _run():
        from sqlalchemy import update
        from backend.app.models.user import UserPushToken

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # last_used가 30일 이상 된 활성 토큰을 expired로 전환 (소프트 삭제)
                result = await db.execute(
                    update(UserPushToken)
                    .where(
                        UserPushToken.last_used < cutoff,
                        UserPushToken.status == "active",
                    )
                    .values(status="expired")
                )
                expired = result.rowcount
                logger.info("cleanup_stale_tokens: 오래된 토큰 %d개 expired 처리 (cutoff=%s)", expired, cutoff)
                return {"status": "ok", "expired": expired}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("cleanup_stale_tokens 오류: %s", exc)
        raise self.retry(exc=exc)


# ── Sprint 2: Delivery Integrity 배치 태스크 ──────────────────────────────


@app.task(
    name="worker.tasks.timeout_pending_deliveries",
    queue="process",
    bind=True,
    max_retries=1,
)
def timeout_pending_deliveries(self):
    """5분 이상 pending인 delivery log를 failed(timeout)로 전환."""

    async def _run():
        from sqlalchemy import update as sa_update
        from backend.app.models.alert_delivery_log import AlertDeliveryLog

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    sa_update(AlertDeliveryLog)
                    .where(
                        AlertDeliveryLog.decision == "pending",
                        AlertDeliveryLog.created_at < cutoff,
                    )
                    .values(
                        decision="failed",
                        failure_reason="timeout",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                logger.info("timeout_pending: %d건 failed(timeout) 처리", result.rowcount)
                return {"timed_out": result.rowcount}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("timeout_pending 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.build_missed_spike_summary",
    queue="process",
    bind=True,
    max_retries=1,
)
def build_missed_spike_summary(self):
    """suppressed(plan_locked/dnd) 기록에서 missed spike 요약 생성. primary 모드만."""

    async def _run():
        from sqlalchemy import select
        from backend.app.models.alert_delivery_log import AlertDeliveryLog
        from backend.app.models.user_missed_spike import UserMissedSpikeSummary

        # pipeline_mode='primary'만 집계 (PRD 9)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(AlertDeliveryLog).where(
                        AlertDeliveryLog.decision == "suppressed",
                        AlertDeliveryLog.suppression_reason.in_(["plan_locked", "dnd"]),
                        AlertDeliveryLog.pipeline_mode == "primary",
                        AlertDeliveryLog.created_at >= cutoff,
                    )
                )
                logs = result.scalars().all()

                created = 0
                for log in logs:
                    # 중복 체크
                    existing = await db.execute(
                        select(UserMissedSpikeSummary).where(
                            UserMissedSpikeSummary.user_id == log.user_id,
                            UserMissedSpikeSummary.spike_event_id == log.spike_event_id,
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    summary = UserMissedSpikeSummary(
                        user_id=log.user_id,
                        cluster_id=log.cluster_id,
                        spike_event_id=log.spike_event_id,
                        reason=log.suppression_reason,
                    )
                    db.add(summary)
                    created += 1

                logger.info("build_missed_spike: %d건 생성", created)
                return {"created": created}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("build_missed_spike 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.reconcile_delivery_logs",
    queue="process",
    bind=True,
    max_retries=1,
)
def reconcile_delivery_logs(self):
    """sent 로그의 토큰 유효성 재확인, missed_spike 보정.

    매일 04:00 UTC 실행.
    - sent인데 해당 유저의 토큰이 모두 expired인 경우 -> failed로 보정
    - suppressed(plan_locked/dnd) 중 missed_spike_summary에 누락된 건 보정
    """

    async def _run():
        from sqlalchemy import select, update as sa_update, and_, exists, not_
        from backend.app.models.alert_delivery_log import AlertDeliveryLog
        from backend.app.models.user_missed_spike import UserMissedSpikeSummary
        from backend.app.models.user import UserPushToken

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        fixed_sent = 0
        fixed_missed = 0

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 1. sent 로그 중 유저의 active 토큰이 없는 경우 -> failed(token_expired)
                sent_logs = await db.execute(
                    select(AlertDeliveryLog).where(
                        AlertDeliveryLog.decision == "sent",
                        AlertDeliveryLog.created_at >= cutoff,
                    )
                )
                for log in sent_logs.scalars().all():
                    active_token = await db.execute(
                        select(UserPushToken.id).where(
                            UserPushToken.user_id == log.user_id,
                            UserPushToken.status == "active",
                        ).limit(1)
                    )
                    if active_token.scalar_one_or_none() is None:
                        log.decision = "failed"
                        log.failure_reason = "token_expired"
                        log.updated_at = now
                        fixed_sent += 1

                # 2. suppressed(plan_locked/dnd) 중 missed_spike_summary 누락 보정
                suppressed_logs = await db.execute(
                    select(AlertDeliveryLog).where(
                        AlertDeliveryLog.decision == "suppressed",
                        AlertDeliveryLog.suppression_reason.in_(["plan_locked", "dnd"]),
                        AlertDeliveryLog.pipeline_mode == "primary",
                        AlertDeliveryLog.created_at >= cutoff,
                    )
                )
                for log in suppressed_logs.scalars().all():
                    if log.spike_event_id is None:
                        continue
                    existing = await db.execute(
                        select(UserMissedSpikeSummary).where(
                            UserMissedSpikeSummary.user_id == log.user_id,
                            UserMissedSpikeSummary.spike_event_id == log.spike_event_id,
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none() is None:
                        summary = UserMissedSpikeSummary(
                            user_id=log.user_id,
                            cluster_id=log.cluster_id,
                            spike_event_id=log.spike_event_id,
                            reason=log.suppression_reason,
                        )
                        db.add(summary)
                        fixed_missed += 1

        logger.info(
            "reconcile_delivery_logs: fixed_sent=%d, fixed_missed=%d",
            fixed_sent, fixed_missed,
        )
        return {"status": "ok", "fixed_sent": fixed_sent, "fixed_missed": fixed_missed}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("reconcile_delivery_logs 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.send_trial_nudges",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_trial_nudges(self):
    """Trial D3/D6 넛지 발송. 매일 09:00 UTC (KST 18:00)."""

    async def _run():
        from sqlalchemy import select
        from sqlalchemy import func
        from backend.app.models.subscription import Subscription
        from backend.app.models.user import User
        from backend.app.models.user_missed_spike import UserMissedSpikeSummary
        from backend.app.models.notification import Notification

        now = datetime.now(timezone.utc)
        results = {"d3": 0, "d6": 0}

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # D3 넛지: trial_start + 3일 이내이면서 오늘이 D3 (72시간~96시간)
                d3_start = now - timedelta(hours=96)
                d3_end = now - timedelta(hours=72)
                d3_subs = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "trial",
                        Subscription.trial_start >= d3_start,
                        Subscription.trial_start < d3_end,
                    )
                )
                for sub in d3_subs.scalars().all():
                    # missed spikes 카운트
                    missed_result = await db.execute(
                        select(func.count())
                        .select_from(UserMissedSpikeSummary)
                        .where(
                            UserMissedSpikeSummary.user_id == sub.user_id,
                            UserMissedSpikeSummary.is_shown == False,
                        )
                    )
                    missed_count = missed_result.scalar() or 0

                    if missed_count > 0:
                        title = f"지난 72시간 스파이크 {missed_count}건 감지"
                        body = "Pro에서 놓친 알림을 실시간으로 받아보세요"
                    else:
                        title = "Pro 체험 중: 상황 요약"
                        body = "현재 관심 지역의 긴장도를 확인하세요"

                    notif = Notification(
                        user_id=sub.user_id,
                        type="trial_nudge",
                        title=title,
                        body=body,
                    )
                    db.add(notif)
                    results["d3"] += 1

                # D6 넛지: trial 만료 1일 전 (144~168시간)
                d6_start = now - timedelta(hours=168)
                d6_end = now - timedelta(hours=144)
                d6_subs = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "trial",
                        Subscription.trial_start >= d6_start,
                        Subscription.trial_start < d6_end,
                    )
                )
                for sub in d6_subs.scalars().all():
                    notif = Notification(
                        user_id=sub.user_id,
                        type="trial_nudge",
                        title="내일 체험이 종료됩니다",
                        body="Pro 구독으로 전환하여 모든 기능을 계속 사용하세요",
                    )
                    db.add(notif)
                    results["d6"] += 1

        logger.info("send_trial_nudges: d3=%d, d6=%d", results["d3"], results["d6"])
        return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_trial_nudges 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 주간 리포트 이메일 발송 ───────────────────────────────────────────────


async def _send_weekly_report_impl():
    """매주 월요일 마케팅 동의 사용자에게 주간 리포트 이메일 발송."""
    import smtplib
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import jinja2
    from sqlalchemy import select, func, text
    from backend.app.models.user import User, UserArea, UserPreference
    from backend.app.models.issue_cluster import IssueCluster
    from backend.app.models.tension_index import TensionIndex

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        logger.warning("send_weekly_report: SMTP 설정 누락 (SMTP_USER/SMTP_PASS), 발송 중단")
        return {"status": "skipped", "reason": "no_smtp_config"}

    # Jinja2 템플릿 로드
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "backend", "app", "templates",
    )
    template_path = os.path.abspath(template_path)
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path),
        autoescape=True,
    )
    template = jinja_env.get_template("weekly_report.html")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # 전체 통계 (모든 사용자 공통)
    async with AsyncSessionLocal() as db:
        total_events_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM normalized_events
                WHERE event_time >= :cutoff AND is_duplicate = FALSE
            """),
            {"cutoff": cutoff},
        )
        total_events = total_events_result.scalar() or 0

        new_clusters_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM issue_clusters
                WHERE created_at >= :cutoff AND severity > 0
            """),
            {"cutoff": cutoff},
        )
        new_clusters = new_clusters_result.scalar() or 0

        crisis_countries_result = await db.execute(
            text("""
                SELECT COUNT(DISTINCT country_code) FROM issue_clusters
                WHERE created_at >= :cutoff AND severity >= 70 AND country_code IS NOT NULL
            """),
            {"cutoff": cutoff},
        )
        crisis_countries = crisis_countries_result.scalar() or 0

        global_stats = {
            "total_events": total_events,
            "new_clusters": new_clusters,
            "crisis_countries": crisis_countries,
        }

        # TOP 10 이슈 클러스터 (전체 사용자 공통)
        top_issues_result = await db.execute(
            select(IssueCluster).where(
                IssueCluster.severity > 0,
                IssueCluster.last_event_at >= cutoff,
            ).order_by(
                IssueCluster.severity.desc(),
                IssueCluster.kscore.desc(),
            ).limit(10)
        )
        top_issues = top_issues_result.scalars().all()

        # 마케팅 동의 사용자 전체 조회
        users_result = await db.execute(
            select(User).where(
                User.marketing_agreed_at.isnot(None),
                User.status == "active",
                User.email.isnot(None),
            )
        )
        all_users = users_result.scalars().all()

    logger.info("send_weekly_report: 대상 사용자 %d명", len(all_users))

    sent_total = 0
    failed_total = 0
    batch_size = 50

    try:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
    except Exception as e:
        logger.error("send_weekly_report: SMTP 연결 실패: %s", e)
        return {"status": "error", "reason": str(e)}

    for batch_start in range(0, len(all_users), batch_size):
        batch = all_users[batch_start:batch_start + batch_size]

        for user in batch:
            try:
                is_pro = user.plan in ("pro", "pro_plus")
                lang = "ko"

                async with AsyncSessionLocal() as db:
                    # 사용자 언어 설정 조회
                    pref_result = await db.execute(
                        select(UserPreference).where(UserPreference.user_id == user.id)
                    )
                    pref = pref_result.scalar_one_or_none()
                    if pref and pref.language:
                        lang = pref.language

                    # Pro/Pro+ 사용자: 관심 국가 긴장도 조회
                    tensions = []
                    if is_pro:
                        areas_result = await db.execute(
                            select(UserArea).where(
                                UserArea.user_id == user.id,
                                UserArea.is_active == True,
                                UserArea.country_code.isnot(None),
                            )
                        )
                        user_areas = areas_result.scalars().all()
                        country_codes = [a.country_code for a in user_areas if a.country_code]

                        if country_codes:
                            tension_result = await db.execute(
                                text("""
                                    SELECT DISTINCT ON (country_code)
                                        country_code, tension_level, raw_score
                                    FROM tension_index
                                    WHERE country_code = ANY(:codes)
                                    ORDER BY country_code, time DESC
                                """),
                                {"codes": country_codes},
                            )
                            tensions = [
                                {
                                    "country_code": row.country_code,
                                    "tension_level": row.tension_level,
                                    "raw_score": row.raw_score,
                                }
                                for row in tension_result.fetchall()
                            ]

                # 템플릿 렌더링
                subject_ko = "WeWantPeace 주간 리포트"
                subject_en = "WeWantPeace Weekly Report"
                subject = subject_ko if lang == "ko" else subject_en

                html_body = template.render(
                    user=user,
                    issues=top_issues,
                    tensions=tensions,
                    stats=global_stats,
                    is_pro=is_pro,
                    lang=lang,
                )

                # 이메일 발송
                msg = MIMEMultipart("alternative")
                msg["From"] = sender
                msg["To"] = user.email
                msg["Subject"] = subject
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                smtp.sendmail(sender, user.email, msg.as_string())

                # 발송 로그 기록
                async with AsyncSessionLocal() as db:
                    async with db.begin():
                        await db.execute(
                            text(
                                "INSERT INTO marketing_email_logs"
                                " (user_id, subject, status)"
                                " VALUES (:uid, :subj, :st)"
                            ),
                            {"uid": str(user.id), "subj": subject, "st": "sent"},
                        )

                sent_total += 1

            except Exception as e:
                logger.warning(
                    "send_weekly_report: 발송 실패 [user=%s, email=%s]: %s",
                    user.id, user.email, e,
                )
                # 실패 로그 기록
                try:
                    async with AsyncSessionLocal() as db:
                        async with db.begin():
                            await db.execute(
                                text(
                                    "INSERT INTO marketing_email_logs"
                                    " (user_id, subject, status)"
                                    " VALUES (:uid, :subj, :st)"
                                ),
                                {
                                    "uid": str(user.id),
                                    "subj": "WeWantPeace Weekly Report",
                                    "st": "failed",
                                },
                            )
                except Exception:
                    pass
                failed_total += 1

        # 배치 간 딜레이 (마지막 배치 제외)
        if batch_start + batch_size < len(all_users):
            import asyncio as _asyncio
            await _asyncio.sleep(0.5)

    try:
        smtp.quit()
    except Exception:
        pass

    logger.info(
        "send_weekly_report 완료: sent=%d, failed=%d",
        sent_total, failed_total,
    )
    return {"status": "ok", "sent": sent_total, "failed": failed_total}


@app.task(name="worker.tasks.send_weekly_report", queue="process")
def send_weekly_report():
    """매주 월요일 주간 리포트 발송."""
    return run_async(_send_weekly_report_impl())


# ── Admin Ops v0.9: KPI Alert Email ──────────────────────────────────────────

async def _send_kpi_alert_email(alerts: list[dict], week_start) -> None:
    """KPI drop alert 이메일을 admin 유저들에게 발송."""
    import smtplib
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from sqlalchemy import select
    from backend.app.models.user import User

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        logger.warning("_send_kpi_alert_email: SMTP 설정 누락, 발송 중단")
        return

    # admin 유저 조회
    async with AsyncSessionLocal() as db:
        admin_result = await db.execute(
            select(User).where(User.role == "admin", User.email.isnot(None), User.status == "active")
        )
        admins = admin_result.scalars().all()

    if not admins:
        logger.info("_send_kpi_alert_email: admin 유저 없음")
        return

    # 이메일 본문 생성
    rows = ""
    for a in alerts:
        rows += f"<tr><td style='padding:8px;border:1px solid #ddd'>{a['kpi']}</td>"
        rows += f"<td style='padding:8px;border:1px solid #ddd'>{a['prev']}</td>"
        rows += f"<td style='padding:8px;border:1px solid #ddd'>{a['curr']}</td>"
        rows += f"<td style='padding:8px;border:1px solid #ddd;color:red'>{a['drop_pct']}%</td></tr>"

    html = f"""<html><body>
    <h2>⚠️ WeWantPeace KPI Alert — Week of {week_start}</h2>
    <p>다음 KPI가 전주 대비 30% 이상 하락했습니다:</p>
    <table style='border-collapse:collapse;width:100%'>
    <tr style='background:#f5f5f5'>
      <th style='padding:8px;border:1px solid #ddd'>KPI</th>
      <th style='padding:8px;border:1px solid #ddd'>Previous</th>
      <th style='padding:8px;border:1px solid #ddd'>Current</th>
      <th style='padding:8px;border:1px solid #ddd'>Drop</th>
    </tr>
    {rows}
    </table>
    <p style='margin-top:16px;color:#666'>어드민 대시보드에서 상세 내용을 확인하세요.</p>
    </body></html>"""

    try:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)

        for admin in admins:
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = sender
                msg["To"] = admin.email
                msg["Subject"] = f"[WeWantPeace] KPI Alert — Week of {week_start}"
                msg.attach(MIMEText(html, "html", "utf-8"))
                smtp.sendmail(sender, admin.email, msg.as_string())
            except Exception as e:
                logger.warning("KPI alert 이메일 발송 실패 [%s]: %s", admin.email, e)

        smtp.quit()
        logger.info("KPI alert 이메일 발송 완료: %d명 admin", len(admins))
    except Exception as e:
        logger.error("KPI alert SMTP 연결 실패: %s", e)


# ── Admin Ops v0.9: Weekly KPI Snapshot ──────────────────────────────────────

@app.task(
    name="worker.tasks.snapshot_weekly_kpi",
    queue="process",
    bind=True,
    max_retries=1,
)
def snapshot_weekly_kpi(self):
    """매주 월요일 자동 KPI 스냅샷 생성."""

    async def _run():
        from sqlalchemy import select, func
        from backend.app.models.app_event import AppEvent
        from backend.app.models.paywall_event import PaywallEvent
        from backend.app.models.subscription import Subscription
        from backend.app.models.user import User
        from backend.app.models.weekly_kpi_snapshot import WeeklyKpiSnapshot

        now = datetime.now(timezone.utc)
        today = now.date()
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)

        week_start_dt = datetime.combine(last_monday, datetime.min.time()).replace(tzinfo=timezone.utc)
        week_end_dt = datetime.combine(last_sunday, datetime.max.time()).replace(tzinfo=timezone.utc)

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 중복 체크
                existing = await db.execute(
                    select(WeeklyKpiSnapshot).where(WeeklyKpiSnapshot.week_start == last_monday)
                )
                if existing.scalar_one_or_none():
                    logger.info("snapshot_weekly_kpi: 이미 존재 (week=%s)", last_monday)
                    return {"status": "exists"}

                # app_events 집계
                ae_q = await db.execute(
                    select(AppEvent.name, func.count())
                    .where(AppEvent.created_at >= week_start_dt, AppEvent.created_at <= week_end_dt)
                    .group_by(AppEvent.name)
                )
                ae_counts = {row[0]: row[1] for row in ae_q.all()}

                auth_success = ae_counts.get("auth_success", 0)
                onboarding_complete = ae_counts.get("onboarding_complete", 0)
                a1_rate = round(onboarding_complete / max(1, auth_success) * 100, 1)

                pw_shown = (await db.execute(
                    select(func.count()).select_from(PaywallEvent)
                    .where(PaywallEvent.action == "shown", PaywallEvent.created_at >= week_start_dt, PaywallEvent.created_at <= week_end_dt)
                )).scalar() or 0
                pw_purchase = (await db.execute(
                    select(func.count()).select_from(PaywallEvent)
                    .where(PaywallEvent.action == "purchase_success", PaywallEvent.created_at >= week_start_dt, PaywallEvent.created_at <= week_end_dt)
                )).scalar() or 0
                paywall_rate = round(pw_purchase / max(1, pw_shown) * 100, 1)

                trial_started = (await db.execute(
                    select(func.count()).select_from(Subscription)
                    .where(Subscription.trial_start.isnot(None), Subscription.trial_start >= week_start_dt, Subscription.trial_start <= week_end_dt)
                )).scalar() or 0
                trial_converted = (await db.execute(
                    select(func.count()).select_from(Subscription)
                    .where(Subscription.trial_start.isnot(None), Subscription.trial_start >= week_start_dt, Subscription.trial_start <= week_end_dt, Subscription.status == "active", Subscription.trial_end.isnot(None))
                )).scalar() or 0
                trial_to_paid = round(trial_converted / max(1, trial_started) * 100, 1)

                d7_start = week_start_dt - timedelta(days=7)
                d7_end = week_start_dt
                d7_cohort = (await db.execute(
                    select(func.count()).select_from(User).where(User.created_at >= d7_start, User.created_at < d7_end, User.status != "deleted")
                )).scalar() or 0
                d7_retained = (await db.execute(
                    select(func.count()).select_from(User).where(User.created_at >= d7_start, User.created_at < d7_end, User.last_active >= week_start_dt, User.status != "deleted")
                )).scalar() or 0
                d7_retention = round(d7_retained / max(1, d7_cohort) * 100, 1)

                # Referral 메트릭
                referral_install = (await db.execute(
                    select(func.count()).select_from(User)
                    .where(User.created_at >= week_start_dt, User.created_at <= week_end_dt, User.referred_by_code.isnot(None))
                )).scalar() or 0
                referral_trial_start = (await db.execute(
                    select(func.count()).select_from(Subscription)
                    .where(
                        Subscription.trial_start.isnot(None),
                        Subscription.trial_start >= week_start_dt,
                        Subscription.trial_start <= week_end_dt,
                    ).where(
                        Subscription.user_id.in_(
                            select(User.id).where(User.referred_by_code.isnot(None))
                        )
                    )
                )).scalar() or 0

                metrics = {**ae_counts, "paywall_shown": pw_shown, "paywall_purchase": pw_purchase, "trial_started": trial_started, "trial_converted": trial_converted, "d7_cohort": d7_cohort, "d7_retained": d7_retained, "referral_install": referral_install, "referral_trial_start": referral_trial_start}
                kpi_data = {"a1_onboarding_rate": a1_rate, "paywall_conversion_rate": paywall_rate, "trial_to_paid_rate": trial_to_paid, "d7_retention_rate": d7_retention}

                # WoW delta
                prev_q = await db.execute(
                    select(WeeklyKpiSnapshot).where(WeeklyKpiSnapshot.week_start == last_monday - timedelta(days=7))
                )
                prev = prev_q.scalar_one_or_none()
                wow_delta = None
                alerts = None
                if prev and prev.kpi:
                    wow_delta = {}
                    alerts = []
                    for k, v in kpi_data.items():
                        prev_val = prev.kpi.get(k, 0)
                        delta = round(v - prev_val, 1)
                        wow_delta[k] = delta
                        if prev_val > 0 and delta / prev_val * 100 <= -30:
                            alerts.append({"kpi": k, "prev": prev_val, "curr": v, "drop_pct": round(delta / prev_val * 100, 1)})
                    if not alerts:
                        alerts = None

                snapshot = WeeklyKpiSnapshot(
                    week_start=last_monday,
                    week_end=last_sunday,
                    metrics=metrics,
                    kpi=kpi_data,
                    wow_delta=wow_delta,
                    alerts=alerts,
                    data_source="auto",
                )
                db.add(snapshot)

        # KPI drop alert 이메일 발송
        if alerts:
            await _send_kpi_alert_email(alerts, last_monday)

        logger.info("snapshot_weekly_kpi 완료: week=%s, kpi=%s, alerts=%s", last_monday, kpi_data, alerts)
        return {"status": "ok", "week_start": str(last_monday), "alerts": alerts}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("snapshot_weekly_kpi 오류: %s", exc)
        raise self.retry(exc=exc)


# ── SNS 자동 포스팅 태스크 ──────────────────────────────────────────────


@app.task(
    name="worker.tasks.generate_daily_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def generate_daily_social(self):
    """매일 Daily Movers SNS 포스트 생성."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED
        if not SOCIAL_AUTOGEN_ENABLED:
            logger.info("generate_daily_social: SOCIAL_AUTOGEN_ENABLED=false, 건너뜀")
            return {"status": "disabled"}

        from worker.social.generators import generate_daily_movers
        from worker.social.telegram_bot import send_review_message

        async with AsyncSessionLocal() as db:
            async with db.begin():
                post = await generate_daily_movers(db)
                if not post:
                    return {"status": "skipped"}

            await send_review_message(post)
            return {"status": "ok", "post_id": str(post.id)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_daily_social 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.generate_spike_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def generate_spike_social(self):
    """미처리 스파이크 이벤트에 대한 SNS 포스트 생성."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED, SPIKE_SOCIAL_SEVERITY_MIN
        if not SOCIAL_AUTOGEN_ENABLED:
            return {"status": "disabled"}

        from sqlalchemy import select
        from backend.app.models.spike_event import SpikeEvent
        from backend.app.models.issue_cluster import IssueCluster
        from backend.app.models.social_post import SocialPost
        from worker.social.generators import generate_spike_alert
        from worker.social.telegram_bot import send_review_message

        created = 0
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(SpikeEvent, IssueCluster)
                    .join(IssueCluster, SpikeEvent.cluster_id == IssueCluster.id)
                    .where(SpikeEvent.severity >= SPIKE_SOCIAL_SEVERITY_MIN)
                    .order_by(SpikeEvent.triggered_at.desc())
                    .limit(10)
                )
                rows = result.all()

                posts_to_notify = []
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                for spike, cluster in rows:
                    # cluster_id + 날짜 기반 dedup (generate_spike_alert와 동일)
                    dedup_key = f"spike_alert:{cluster.id}:{today}"
                    existing = await db.execute(
                        select(SocialPost).where(SocialPost.dedup_key == dedup_key)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    post = await generate_spike_alert(spike, cluster, db)
                    if post:
                        posts_to_notify.append(post)
                        created += 1

            for post in posts_to_notify:
                await send_review_message(post)

        return {"status": "ok", "created": created}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_spike_social 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.generate_weekly_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def generate_weekly_social(self):
    """매주 월요일 Weekly Recap SNS 포스트 생성."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED
        if not SOCIAL_AUTOGEN_ENABLED:
            return {"status": "disabled"}

        from worker.social.generators import generate_weekly_recap
        from worker.social.telegram_bot import send_review_message

        async with AsyncSessionLocal() as db:
            async with db.begin():
                post = await generate_weekly_recap(db)
                if not post:
                    return {"status": "skipped"}

            await send_review_message(post)
            return {"status": "ok", "post_id": str(post.id)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_weekly_social 오류: %s", exc)
        raise self.retry(exc=exc)


async def _publish_post_to_platforms(
    db,
    post,
    x_enabled: bool,
    threads_enabled: bool,
    instagram_enabled: bool = False,
) -> bool:
    """단일 포스트를 X/Threads/Instagram에 발행. 성공 여부 반환."""
    from sqlalchemy import select
    from backend.app.models.social_post import SocialPostPlatform

    all_ok = True

    # Threads/Instagram에 이미지가 필요하면 Supabase Storage에 업로드
    if (threads_enabled or instagram_enabled) and post.image_url and not post.image_url.startswith(("http://", "https://")):
        from worker.social.image_uploader import upload_image
        public_url = upload_image(post.image_url, str(post.id))
        if public_url:
            post.image_url = public_url

    # X (Twitter)
    if x_enabled:
        existing_x = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == "x",
            )
        )
        x_record = existing_x.scalar_one_or_none()

        if not x_record:
            from worker.social.adapters.x_adapter import publish as x_publish
            platform_id, error = x_publish(post)
            x_record = SocialPostPlatform(
                post_id=post.id,
                platform="x",
                platform_post_id=platform_id,
                status="published" if platform_id else "failed",
                error_message=error,
                published_at=datetime.now(timezone.utc) if platform_id else None,
            )
            db.add(x_record)
            if not platform_id:
                all_ok = False
        elif x_record.status == "skipped":
            pass  # 의도적 스킵
        elif x_record.status == "failed":
            all_ok = False

    # Threads
    if threads_enabled:
        existing_th = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == "threads",
            )
        )
        th_record = existing_th.scalar_one_or_none()

        if not th_record:
            from worker.social.adapters.threads_adapter import publish as threads_publish
            platform_id, error = threads_publish(post)
            th_record = SocialPostPlatform(
                post_id=post.id,
                platform="threads",
                platform_post_id=platform_id,
                status="published" if platform_id else "failed",
                error_message=error,
                published_at=datetime.now(timezone.utc) if platform_id else None,
            )
            db.add(th_record)
            if not platform_id:
                all_ok = False
        elif th_record.status == "skipped":
            pass  # 의도적 스킵
        elif th_record.status == "failed":
            all_ok = False

    # Instagram
    if instagram_enabled:
        existing_ig = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == "instagram",
            )
        )
        ig_record = existing_ig.scalar_one_or_none()

        if not ig_record:
            from worker.social.adapters.instagram_adapter import publish as ig_publish
            platform_id, error = ig_publish(post)
            ig_record = SocialPostPlatform(
                post_id=post.id,
                platform="instagram",
                platform_post_id=platform_id,
                status="published" if platform_id else "failed",
                error_message=error,
                published_at=datetime.now(timezone.utc) if platform_id else None,
            )
            db.add(ig_record)
            if not platform_id:
                all_ok = False
        elif ig_record.status == "skipped":
            pass  # 의도적 스킵
        elif ig_record.status == "failed":
            all_ok = False

    return all_ok


@app.task(
    name="worker.tasks.publish_approved_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def publish_approved_social(self):
    """approved 상태 포스트를 X/Threads/Instagram에 발행."""

    async def _run():
        from sqlalchemy import select
        from backend.app.models.social_post import SocialPost
        from worker.social.config import (
            SOCIAL_PLATFORM_X_ENABLED,
            SOCIAL_PLATFORM_THREADS_ENABLED,
            SOCIAL_PLATFORM_INSTAGRAM_ENABLED,
        )

        published = 0
        failed = 0

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(SocialPost)
                    .where(SocialPost.status == "approved")
                    .order_by(SocialPost.approved_at.asc())
                    .limit(5)
                    .with_for_update(skip_locked=True)
                )
                posts = result.scalars().all()

                # 먼저 publishing 상태로 전환 (다른 워커가 동일 포스트를 잡지 못하게)
                for post in posts:
                    post.status = "publishing"
                await db.flush()

            # 실제 발행은 별도 트랜잭션 (외부 API 호출이 길어질 수 있으므로)
            async with db.begin():
                for post in posts:
                    ok = await _publish_post_to_platforms(
                        db, post,
                        SOCIAL_PLATFORM_X_ENABLED,
                        SOCIAL_PLATFORM_THREADS_ENABLED,
                        SOCIAL_PLATFORM_INSTAGRAM_ENABLED,
                    )
                    if ok:
                        post.status = "published"
                        post.published_at = datetime.now(timezone.utc)
                        published += 1
                    else:
                        post.status = "failed"
                        failed += 1

        if published or failed:
            logger.info("publish_approved_social: published=%d, failed=%d", published, failed)
        return {"status": "ok", "published": published, "failed": failed}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("publish_approved_social 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.send_daily_social_report",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_daily_social_report(self):
    """매일 SNS 운영 일일 리포트 Telegram 전송."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED
        if not SOCIAL_AUTOGEN_ENABLED:
            return {"status": "disabled"}

        from worker.social.reporting import send_daily_ops_report
        async with AsyncSessionLocal() as db:
            return await send_daily_ops_report(db)

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_daily_social_report 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.send_weekly_social_report",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_weekly_social_report(self):
    """매주 SNS 운영 주간 리포트 Telegram 전송."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED
        if not SOCIAL_AUTOGEN_ENABLED:
            return {"status": "disabled"}

        from worker.social.reporting import send_weekly_ops_report
        async with AsyncSessionLocal() as db:
            return await send_weekly_ops_report(db)

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_weekly_social_report 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.aggregate_link_clicks",
    queue="process",
    bind=True,
    max_retries=1,
)
def aggregate_link_clicks(self):
    """단축 링크 클릭 수 집계 (1시간마다)."""

    async def _run():
        from sqlalchemy import select, func, update
        from backend.app.models.short_link import ShortLink, LinkClick

        async with AsyncSessionLocal() as db:
            async with db.begin():
                counts_q = await db.execute(
                    select(LinkClick.link_id, func.count().label("cnt"))
                    .group_by(LinkClick.link_id)
                )
                updated = 0
                for row in counts_q.all():
                    await db.execute(
                        update(ShortLink)
                        .where(ShortLink.id == row.link_id)
                        .values(click_count=row.cnt)
                    )
                    updated += 1

        logger.info("aggregate_link_clicks: %d개 링크 업데이트", updated)
        return {"status": "ok", "updated": updated}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("aggregate_link_clicks 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 서비스 모니터링 ──────────────────────────────────────────────────────


@app.task(
    name="worker.tasks.monitor_service_health",
    queue="process",
    bind=True,
    max_retries=1,
)
def monitor_service_health(self):
    """서비스 헬스 체크 (5분마다)."""

    async def _run():
        from worker.social.monitor import check_service_health, send_monitoring_alert
        results = await check_service_health()
        await send_monitoring_alert(results)
        ok_count = sum(1 for r in results if r.ok)
        return {"status": "ok", "checks": len(results), "healthy": ok_count}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("monitor_service_health 오류: %s", exc)
        raise self.retry(exc=exc)


# ── P1 파이프라인 품질 ──────────────────────────────────────────────────────


@app.task(
    name="worker.tasks.evaluate_source_reliability",
    queue="process",
    bind=True,
    max_retries=1,
)
def evaluate_source_reliability(self):
    """소스 신뢰도 자동 평가 (주간 배치). T9

    소스 채널별 join_rate(클러스터 합류율), solo_rate(단독 이벤트율),
    severity_dev(평균 심각도 편차)를 계산하여 어드민 텔레그램 리포트 전송.
    """

    async def _run():
        import os
        from sqlalchemy import select, func, case, cast, Float as SAFloat
        from backend.app.models.source_channel import SourceChannel
        from backend.app.models.raw_event import RawEvent
        from backend.app.models.normalized_event import NormalizedEvent
        from backend.app.models.issue_cluster import ClusterEvent

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            # 소스 채널 목록
            channels_q = await db.execute(
                select(SourceChannel).where(SourceChannel.is_active == True)  # noqa: E712
            )
            channels = {ch.id: ch for ch in channels_q.scalars().all()}

            if not channels:
                return {"status": "no_channels"}

            # 지난 7일 normalized_events 소스별 통계
            # join: raw_event → source_channel_id
            joined_subq = (
                select(NormalizedEvent.id)
                .join(ClusterEvent, ClusterEvent.event_id == NormalizedEvent.id)
                .where(NormalizedEvent.event_time >= week_ago)
                .correlate(NormalizedEvent)
            ).exists()

            stats_q = await db.execute(
                select(
                    RawEvent.source_channel_id,
                    func.count(NormalizedEvent.id).label("total"),
                    func.sum(
                        case((joined_subq, 1), else_=0)
                    ).label("joined"),
                    func.avg(cast(NormalizedEvent.severity, SAFloat)).label("avg_severity"),
                    func.stddev(cast(NormalizedEvent.severity, SAFloat)).label("severity_dev"),
                )
                .join(NormalizedEvent, NormalizedEvent.raw_event_id == RawEvent.id)
                .where(NormalizedEvent.event_time >= week_ago)
                .where(RawEvent.source_channel_id.isnot(None))
                .group_by(RawEvent.source_channel_id)
            )
            rows = stats_q.all()

            if not rows:
                return {"status": "no_events_this_week"}

            # 리포트 생성
            lines = [f"📊 <b>소스 신뢰도 주간 리포트</b>", f"기간: {week_ago.date()} ~ {now.date()}", ""]

            for row in sorted(rows, key=lambda r: r.total, reverse=True):
                ch = channels.get(row.source_channel_id)
                if not ch:
                    continue
                total = row.total or 0
                joined = row.joined or 0
                join_rate = (joined / total * 100) if total > 0 else 0
                solo_rate = 100 - join_rate
                sev_dev = round(row.severity_dev or 0, 1)
                avg_sev = round(row.avg_severity or 0, 1)

                # 경고 표시
                warn = ""
                if join_rate < 30:
                    warn += " ⚠️낮은합류"
                if sev_dev > 20:
                    warn += " ⚠️편차큼"

                lines.append(
                    f"<b>{ch.display_name}</b> [{ch.tier}] — {total}건\n"
                    f"  합류 {join_rate:.0f}% · 단독 {solo_rate:.0f}% · "
                    f"심각도 평균 {avg_sev} (σ {sev_dev}){warn}"
                )

            report_text = "\n".join(lines)

            # Telegram 전송
            tg_token = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
            tg_chat = os.getenv("SOCIAL_TG_CHAT_ID", "")
            if tg_token and tg_chat:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"https://api.telegram.org/bot{tg_token}/sendMessage",
                            json={"chat_id": tg_chat, "text": report_text, "parse_mode": "HTML"},
                        )
                except Exception as e:
                    logger.warning("소스 신뢰도 텔레그램 전송 실패: %s", e)

            logger.info("evaluate_source_reliability: %d개 소스 분석 완료", len(rows))
            return {"status": "ok", "sources_analyzed": len(rows)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("evaluate_source_reliability 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.detect_severity_outliers",
    queue="process",
    bind=True,
    max_retries=1,
)
def detect_severity_outliers(self):
    """Severity 이상치 감지 + 플래그 (매일). T10

    활성 클러스터 내 이벤트의 severity 표준편차 > 20이면 is_flagged=True.
    """

    async def _run():
        from sqlalchemy import select, func, cast, Float as SAFloat
        from backend.app.models.issue_cluster import IssueCluster, ClusterEvent
        from backend.app.models.normalized_event import NormalizedEvent

        async with AsyncSessionLocal() as db:
            # 활성 클러스터별 severity stddev 계산
            stddev_q = await db.execute(
                select(
                    ClusterEvent.cluster_id,
                    func.stddev(cast(NormalizedEvent.severity, SAFloat)).label("sev_std"),
                    func.count(NormalizedEvent.id).label("ev_count"),
                )
                .join(NormalizedEvent, NormalizedEvent.id == ClusterEvent.event_id)
                .join(IssueCluster, IssueCluster.id == ClusterEvent.cluster_id)
                .where(IssueCluster.is_active == True)  # noqa: E712
                .group_by(ClusterEvent.cluster_id)
                .having(func.count(NormalizedEvent.id) >= 3)  # 이벤트 3개 이상만
            )
            rows = stddev_q.all()

            flagged_ids = []
            unflagged_ids = []
            for row in rows:
                if row.sev_std and row.sev_std > 20:
                    flagged_ids.append(row.cluster_id)
                else:
                    unflagged_ids.append(row.cluster_id)

            # 플래그 설정
            if flagged_ids:
                from sqlalchemy import update
                await db.execute(
                    update(IssueCluster)
                    .where(IssueCluster.id.in_(flagged_ids))
                    .values(is_flagged=True)
                )

            # 기존 플래그 해제 (이상치가 아닌 것)
            if unflagged_ids:
                from sqlalchemy import update
                await db.execute(
                    update(IssueCluster)
                    .where(IssueCluster.id.in_(unflagged_ids))
                    .where(IssueCluster.is_flagged == True)  # noqa: E712
                    .values(is_flagged=False)
                )

            await db.commit()

            logger.info(
                "detect_severity_outliers: %d개 클러스터 분석, %d개 플래그",
                len(rows), len(flagged_ids),
            )
            return {"status": "ok", "analyzed": len(rows), "flagged": len(flagged_ids)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("detect_severity_outliers 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.deactivate_stale_clusters",
    queue="process",
    bind=True,
    max_retries=1,
)
def deactivate_stale_clusters(self):
    """Stale 클러스터 자동 비활성화 (매일). T11

    72시간 이상 이벤트 미추가 + severity < 50 → is_active=False.
    """

    async def _run():
        from sqlalchemy import select, update, func
        from backend.app.models.issue_cluster import IssueCluster

        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(hours=72)

        async with AsyncSessionLocal() as db:
            # 대상 클러스터 수 먼저 확인
            count_q = await db.execute(
                select(func.count(IssueCluster.id)).where(
                    IssueCluster.is_active == True,  # noqa: E712
                    IssueCluster.last_event_at < stale_cutoff,
                    IssueCluster.severity < 50,
                )
            )
            target_count = count_q.scalar() or 0

            if target_count > 0:
                await db.execute(
                    update(IssueCluster)
                    .where(
                        IssueCluster.is_active == True,  # noqa: E712
                        IssueCluster.last_event_at < stale_cutoff,
                        IssueCluster.severity < 50,
                    )
                    .values(is_active=False)
                )
                await db.commit()

            logger.info("deactivate_stale_clusters: %d개 비활성화", target_count)
            return {"status": "ok", "deactivated": target_count}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("deactivate_stale_clusters 오류: %s", exc)
        raise self.retry(exc=exc)
