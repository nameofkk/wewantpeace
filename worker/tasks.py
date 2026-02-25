"""
Celery 태스크 정의.
수집 / 처리 / 계산 파이프라인.
"""
import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from worker.celery_app import app
from backend.app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def run_async(coro):
    """동기 Celery 태스크에서 비동기 코드 실행 헬퍼.

    Celery fork 워커에서 매 태스크마다 새 이벤트 루프를 생성한다.
    asyncpg 커넥션 풀이 이전 루프에 바인딩된 연결을 재사용하려 하면
    'Future attached to a different loop' 오류가 발생하므로,
    루프를 닫기 전에 engine.dispose()로 풀 연결을 먼저 정리한다.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # 커넥션 풀 정리: loop 닫기 전 필수 (asyncpg Future loop 충돌 방지)
        try:
            from backend.app.core.database import engine
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)


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
        async with AsyncSessionLocal() as db:
            collector = RSSCollector()
            results = await collector.collect_all(db)
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

                norm = await asyncio.to_thread(
                    normalize,
                    raw_text=raw_event.raw_text,
                    source_tier=tier,
                    collected_at=raw_event.collected_at,
                    source_title=rss_title,
                    published_at=published_at,
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
                    event_time=norm.event_time,
                )
                db.add(ne)
                await db.flush()

                # 6. 중복 아닌 경우 클러스터 할당 + 스파이크 평가
                cluster_id = None
                is_spike = False

                just_verified = False
                if not is_dup:
                    cluster, just_verified = await assign_cluster(ne, db)
                    if cluster is not None:
                        cluster_id = str(cluster.id)

                        # 스파이크 감지 (Redis 필요)
                        try:
                            redis = get_redis()
                            is_spike = await evaluate_spike(
                                cluster_id=cluster_id,
                                cluster_key=cluster.cluster_key,
                                severity=cluster.severity,
                                redis=redis,
                            )
                            if is_spike and not cluster.is_spike:
                                from datetime import datetime, timezone
                                cluster.is_spike = True
                                cluster.spike_at = datetime.now(timezone.utc)
                        except Exception as e:
                            logger.warning("스파이크 감지 오류 (무시): %s", e)

                # 7. 처리 완료 플래그
                raw_event.processed = True

        # 스파이크이면 알림 태스크 체이닝 (트랜잭션 밖에서)
        if is_spike and cluster_id:
            push_spike_alert.delay(cluster_id)

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
    """트렌딩 키워드 계산 (15분마다)."""

    async def _run():
        from worker.processor.trending_engine import calculate_global_trending
        async with AsyncSessionLocal() as db:
            async with db.begin():
                results = await calculate_global_trending(db)
                logger.info("트렌딩 계산 완료: %d개", len(results))
                return {"status": "ok", "count": len(results)}

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
        from datetime import datetime, timezone, timedelta

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
                            # 스파이크 재평가
                            try:
                                redis = get_redis()
                                is_spike = await evaluate_spike(
                                    cluster_id=str(cluster.id),
                                    cluster_key=cluster.cluster_key,
                                    severity=cluster.severity,
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
def push_spike_alert(self, cluster_id: str):
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
                        user.plan = "free"
                        downgraded += 1

                logger.info("expire_subscriptions: %d명 → free 다운그레이드", downgraded)
                return {"status": "ok", "downgraded": downgraded}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("expire_subscriptions 오류: %s", exc)
        raise self.retry(exc=exc)
