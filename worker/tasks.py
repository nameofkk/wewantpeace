"""
Celery 태스크 정의.
수집 / 처리 / 계산 파이프라인.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta, UTC
from email.utils import parsedate_to_datetime

import redis as _sync_redis

from worker.celery_app import app
from backend.app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ── Sync Redis (heartbeat 기록용) ─────────────────────────────────────────────
_sync_redis_client: _sync_redis.Redis | None = None


def _get_sync_redis() -> _sync_redis.Redis:
    """Celery 워커(동기)에서 사용할 sync Redis 클라이언트."""
    global _sync_redis_client
    if _sync_redis_client is None:
        _sync_redis_client = _sync_redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
    return _sync_redis_client


def _send_email(to: str, subject: str, html: str, from_addr: str | None = None):
    """이메일 발송. RESEND_API_KEY 있으면 Resend HTTP API, 없으면 SMTP 폴백."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key:
        import json
        import urllib.request
        sender = from_addr or "WeWantPeace <noreply@wewantpeace.live>"
        data = json.dumps({"from": sender, "to": [to], "subject": subject, "html": html}).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json", "User-Agent": "WeWantPeace/1.0"},
        )
        urllib.request.urlopen(req, timeout=15)
    else:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASSWORD", "")
        sender = from_addr or smtp_user
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(sender, to, msg.as_string())
        smtp.quit()


def _record_heartbeat(task_name: str) -> None:
    """태스크 시작 시 Redis에 마지막 실행 시각 기록."""
    try:
        r = _get_sync_redis()
        r.set(f"celery:last_run:{task_name}", datetime.now(UTC).isoformat(), ex=3600)
    except Exception:
        logger.debug("heartbeat 기록 실패: %s", task_name, exc_info=True)


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
    _record_heartbeat("collect_telegram_channels")

    async def _run():
        from worker.collector.telegram_collector import TelegramCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = TelegramCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                try:
                    await db.flush()   # ID 생성을 위해 flush 먼저
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
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
    """RSS 피드 수집 (5분마다). 이전 사이클이 실행 중이면 skip."""
    _record_heartbeat("collect_rss")

    async def _run():
        from worker.collector.rss_collector import RSSCollector
        from backend.app.core.redis import get_redis
        redis = get_redis()

        # 중복 실행 방지 (이전 사이클이 아직 실행 중이면 skip)
        lock_key = "lock:collect_rss"
        # lock TTL 20분 (64피드 순회에 ~10분 소요)
        acquired = await redis.set(lock_key, "1", ex=1200, nx=True)
        if not acquired:
            # stale lock 감지: TTL이 원래 설정보다 많이 남아있으면 이전 배포 잔여 lock
            ttl = await redis.ttl(lock_key)
            if ttl and ttl > 1200:
                await redis.delete(lock_key)
                logger.warning("RSS stale lock 삭제 (TTL=%ds), 재시도", ttl)
                acquired = await redis.set(lock_key, "1", ex=1200, nx=True)
            if not acquired:
                logger.info("RSS 수집 skip: 이전 사이클 실행 중")
                return {"status": "skipped", "reason": "already_running"}

        try:
            async with AsyncSessionLocal() as db:
                collector = RSSCollector()
                # collect_all 내부에서 피드별 flush+commit 처리 완료
                results = await collector.collect_all(db, redis=redis)
                total = sum(r.collected for r in results)
                # 처리 파이프라인 체이닝 (이미 commit 완료된 이벤트만)
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                if all_ids:
                    for i, raw_id in enumerate(all_ids):
                        process_raw_event.delay(raw_id)
                        if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                            await asyncio.sleep(0.5)
                    logger.info("RSS 수집 완료: 총 %d개 새 이벤트 → process_raw_event %d개 트리거", total, len(all_ids))
                else:
                    logger.info("RSS 수집 완료: 총 %d개 새 이벤트", total)
                return {"total_collected": total, "feeds": len(results)}
        finally:
            await redis.delete(lock_key)

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
    _record_heartbeat("collect_gdelt")

    async def _run():
        from worker.collector.gdelt_collector import GDELTCollector
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            collector = GDELTCollector()
            redis = get_redis()
            results = await collector.collect_all(db, redis=redis)
            total = sum(r.collected for r in results)
            if total > 0:
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
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
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
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
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
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
    name="worker.tasks.collect_usgs",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def collect_usgs(self):
    """USGS 지진 API 수집 (5분마다, M5.0+)."""
    _record_heartbeat("collect_usgs")

    async def _run():
        from worker.collector.usgs_earthquake import USGSEarthquakeCollector
        async with AsyncSessionLocal() as db:
            collector = USGSEarthquakeCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
                logger.info("USGS 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("USGS 수집 완료: 새 이벤트 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("USGS 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_travel_advisory",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def collect_travel_advisory(self):
    """Travel Advisory 수집 (6시간마다) - US → Korea → UK 순차 실행."""

    async def _run():
        from worker.collector.travel_advisory import (
            TravelAdvisoryCollector,
            KoreaTravelAdvisoryCollector,
            UKTravelAdvisoryCollector,
        )

        all_results = []
        async with AsyncSessionLocal() as db:
            # 1) US State Dept
            us_collector = TravelAdvisoryCollector()
            us_results = await us_collector.collect_all(db)
            all_results.extend(us_results)

            # 2) Korea MOFA (API 키 없으면 내부에서 skip)
            kr_collector = KoreaTravelAdvisoryCollector()
            kr_results = await kr_collector.collect_all(db)
            all_results.extend(kr_results)

            # 3) UK FCDO (인증 불요)
            uk_collector = UKTravelAdvisoryCollector()
            uk_results = await uk_collector.collect_all(db)
            all_results.extend(uk_results)

            total = sum(r.collected for r in all_results)
            if total > 0:
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    raise
                all_ids = []
                for r in all_results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
                # 소스별 통계 로깅
                for r in all_results:
                    logger.info(
                        "%s 수집: collected=%d, skipped=%d, errors=%s",
                        r.display_name, r.collected, r.skipped, r.errors,
                    )
                logger.info("Travel Advisory 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("Travel Advisory 수집 완료: 새 이벤트 없음 (US/Korea/UK)")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("Travel Advisory 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_economic_data",
    queue="collect",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def collect_economic_data(self):
    """경제 데이터 수집 (매일 04:00 UTC) — IMF/World Bank/Frankfurter"""
    _record_heartbeat("collect_economic_data")

    async def _run():
        from worker.collector.economic_data_collector import collect_all_economic_data
        async with AsyncSessionLocal() as db:
            results = await collect_all_economic_data(db)
            logger.info("경제 데이터 수집 완료: %s", results)
            return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("경제 데이터 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_market_data",
    queue="collect",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def collect_market_data(self):
    """시장 데이터 수집 (6시간마다) — yfinance 원자재/지수 + 구조화 여행경보"""
    _record_heartbeat("collect_market_data")

    async def _run():
        from worker.collector.economic_data_collector import collect_market_data
        async with AsyncSessionLocal() as db:
            results = await collect_market_data(db)
            logger.info("시장 데이터 수집 완료: %s", results)
            return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("시장 데이터 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.pregenerate_impact_briefs",
    queue="process",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def pregenerate_impact_briefs(self):
    """Impact Brief 사전 생성 — 상위 이슈 × 주요 홈 국가 조합을 미리 캐싱.

    Batch API 대신 일반 API를 사용하되, 스케줄러로 오프피크 시간에 실행하여
    사용자 요청 시 캐시 히트율을 극대화합니다.
    캐시 TTL 12시간 → 12시간마다 실행.
    """
    _record_heartbeat("pregenerate_impact_briefs")

    async def _run():
        import json
        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster
        from backend.app.routers.impact import (
            _generate_impact_brief,
            _brief_cache_key,
        )
        from backend.app.core.redis import get_redis

        HOME_COUNTRIES = ["KR", "US", "JP", "CN", "DE", "GB", "AU", "IN", "BR", "TW"]
        generated = 0
        skipped = 0

        async with AsyncSessionLocal() as db:
            # 상위 30개 활성 클러스터 (severity × kscore 순)
            clusters_q = await db.execute(
                select(IssueCluster)
                .where(
                    IssueCluster.is_active == True,
                    IssueCluster.severity > 20,
                    IssueCluster.kscore > 1.0,
                )
                .order_by(
                    (IssueCluster.severity * IssueCluster.kscore).desc()
                )
                .limit(30)
            )
            clusters = clusters_q.scalars().all()

            redis = get_redis()
            if not redis:
                logger.warning("pregenerate: Redis 미연결, 스킵")
                return {"generated": 0, "skipped": 0}

            for cluster in clusters:
                for home in HOME_COUNTRIES:
                    cache_key = _brief_cache_key(str(cluster.id), home)
                    # 이미 캐시에 있으면 스킵
                    existing = await redis.get(cache_key)
                    if existing:
                        skipped += 1
                        continue

                    try:
                        brief = await _generate_impact_brief(cluster, home, "ko", db)
                        response_data = {
                            "cluster_id": str(cluster.id),
                            "title": cluster.title or "",
                            "title_ko": cluster.title_ko,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "cached": False,
                            **brief,
                        }
                        await redis.set(
                            cache_key,
                            json.dumps(response_data),
                            ex=12 * 3600,
                        )
                        generated += 1
                    except Exception as e:
                        logger.warning(
                            "pregenerate_brief_error cluster=%s home=%s: %s",
                            cluster.id, home, e,
                        )

                    # Rate limiting: OpenAI API 보호
                    await asyncio.sleep(0.3)

        logger.info(
            "pregenerate_impact_briefs 완료: generated=%d skipped=%d",
            generated, skipped,
        )
        return {"generated": generated, "skipped": skipped}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("pregenerate_impact_briefs 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.prewarm_impact_summaries",
    queue="process",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def prewarm_impact_summaries(self):
    """Impact Summary 캐시 사전 워밍 — 인기 국가 × plan × lang 조합.

    /impact/summary 엔드포인트의 캐시를 사전 생성하여
    사용자 요청 시 항상 캐시 히트를 보장합니다.
    캐시 TTL 30분 → 25분마다 실행.
    """
    _record_heartbeat("prewarm_impact_summaries")

    async def _run():
        from backend.app.routers.impact import _build_impact_summary

        HOME_COUNTRIES = ["KR", "US", "JP", "CN", "DE", "GB", "AU", "IN", "BR", "TW", ""]
        PLANS = ["free", "pro"]
        LANGS = ["ko", "en"]
        generated = 0

        async with AsyncSessionLocal() as db:
            for home in HOME_COUNTRIES:
                for plan in PLANS:
                    for lang in LANGS:
                        try:
                            # force=True 필수 — 캐시 히트로 조기 반환하면
                            # 만료 전 갱신이 불가능해져 워밍이 무의미해진다.
                            await _build_impact_summary(home, plan, lang, db, force=True)
                            generated += 1
                        except Exception as e:
                            logger.warning(
                                "prewarm_summary_error home=%s plan=%s lang=%s: %s",
                                home or "global", plan, lang, e,
                            )

        logger.info("prewarm_impact_summaries 완료: generated=%d", generated)
        return {"generated": generated}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("prewarm_impact_summaries 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.process_raw_event",
    queue="process",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    retry_backoff=True,
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
        from worker.processor.calibration import KSCORE_MIN
        from backend.app.core.redis import get_redis

        # Idempotency lock: 같은 이벤트가 동시에 2번 처리되는 것 방지
        redis = get_redis()
        lock_key = f"process_raw_event:{raw_event_id}"
        if not await redis.set(lock_key, "1", nx=True, ex=300):
            logger.info("Skipping duplicate event %s", raw_event_id)
            return {"status": "duplicate_lock", "raw_event_id": raw_event_id}

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
                elif (raw_event.source_type == "api"
                      and raw_event.raw_metadata
                      and raw_event.raw_metadata.get("source_tier")):
                    tier = raw_event.raw_metadata["source_tier"]

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

                    s_body_ko = _translate_to_korean(raw_event.raw_text[:500])
                    from worker.processor.normalizer import _classify_sub_topic
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

                # 3-2. 오래된 뉴스 필터: published_at이 7일 이상 과거면 severity 대폭 하향
                # (워싱턴 항공기 충돌 등 회고 기사가 현재 이슈로 표시되는 문제 방지)
                _event_time = norm.event_time or published_at or raw_event.collected_at
                if _event_time:
                    _age_hours = (datetime.now(timezone.utc) - _event_time).total_seconds() / 3600
                    if _age_hours > 168:  # 7일 = 168시간
                        _orig_sev = norm.severity
                        norm.severity = min(norm.severity, 20)
                        logger.info(
                            "오래된 뉴스 감지 (%.0f시간 전): severity %d→%d, title=%s",
                            _age_hours, _orig_sev, norm.severity, norm.title[:60],
                        )

                # 4. 중복 확인
                is_dup = await check_duplicate(norm.dedup_key, db)

                # 5. NormalizedEvent 저장
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

                # 6. 중복 아닌 경우 클러스터 할당 + KScore 기반 알림 트리거
                cluster_id = None

                just_verified = False
                should_alert_fast = False
                if not is_dup:
                    cluster, just_verified = await assign_cluster(ne, db)
                    if cluster is not None:
                        cluster_id = str(cluster.id)

                        # v7: KScore 기반 알림 트리거 (스파이크 감지 대체)
                        from worker.processor.calibration import ALERT_SEVERITY_MIN
                        if cluster.kscore >= KSCORE_MIN and cluster.severity >= ALERT_SEVERITY_MIN:
                            try:
                                redis = get_redis()
                                fast_key = f"alert:fast:{cluster_id}"
                                if not await redis.exists(fast_key):
                                    should_alert_fast = True
                            except Exception as e:
                                logger.warning("KScore 알림 트리거 체크 오류 (무시): %s", e)

                        # 트랜잭션 밖에서 사용하기 위해 로컬 변수에 저장
                        _is_verified = cluster.is_verified

                # 7. 처리 완료 플래그
                raw_event.processed = True

        # v7: KScore 기반 알림 태스크 체이닝 (트랜잭션 밖에서)
        if should_alert_fast and cluster_id:
            alert_kind = "combined" if _is_verified else "fast"
            push_alert.delay(cluster_id, alert_kind)
            # combined은 이미 verified 레인을 포함하므로 별도 verified 불필요
        elif just_verified and cluster_id:
            # fast 트리거 없이 verified만 전환된 경우에만 별도 발송
            push_alert.delay(cluster_id, "verified")

        return {
            "status": "ok",
            "raw_event_id": raw_event_id,
            "is_duplicate": is_dup,
            "cluster_id": cluster_id,
            "topic": norm.topic,
            "severity": norm.severity,
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
    """긴장도 지수 계산 (5분마다)."""
    _record_heartbeat("calculate_tension")
    # 동시 실행 방지 (Redis lock)
    r = _get_sync_redis()
    lock_key = "lock:calculate_tension"
    if not r.set(lock_key, "1", nx=True, ex=300):
        logger.info("calculate_tension 이미 실행 중, 스킵")
        return {"status": "skipped", "reason": "already_running"}

    async def _run():
        from worker.processor.tension_calculator import calculate_all_tensions
        from backend.app.core.redis import get_redis
        async with AsyncSessionLocal() as db:
            async with db.begin():
                results = await calculate_all_tensions(db)
                logger.info("긴장도 계산 완료: %d개국", len(results))
        # DB 커밋 후 캐시 무효화 — 다음 /tension/all 호출 시 신선한 DB 값 사용
        try:
            redis = get_redis()
            await redis.delete("tension:all:cache")
        except Exception as e:
            logger.warning("tension:all:cache 무효화 실패 (무시): %s", e)
        return {"status": "ok", "countries": len(results)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("긴장도 계산 오류: %s", exc)
        raise self.retry(exc=exc)
    finally:
        try:
            r.delete(lock_key)
        except Exception:
            pass


@app.task(
    name="worker.tasks.calculate_trending",
    queue="process",
    bind=True,
    max_retries=2,
)
def calculate_trending(self):
    """트렌딩 키워드 계산 (5분마다). 분산 클러스터 자동 병합 포함."""
    # 동시 실행 방지 (Redis lock)
    r = _get_sync_redis()
    lock_key = "lock:calculate_trending"
    if not r.set(lock_key, "1", nx=True, ex=300):
        logger.info("calculate_trending 이미 실행 중, 스킵")
        return {"status": "skipped", "reason": "already_running"}

    async def _merge_fragmented_clusters(db):
        """같은 cluster_key 또는 같은 국가+관련토픽의 분산된 클러스터를 병합 (보수적).

        병합 조건:
        Phase 1 — 같은 cluster_key 병합 (기존):
        - 8개 토픽 (conflict/terror/coup + diplomacy/maritime/protest/sanctions/cyber)
        - cluster_key가 '0000'으로 시작하지 않을 것 (위치 미상 = 혼합 위험)
        - winner의 event_count가 100 이하일 때만
        - loser의 last_event_at이 winner 기준 72시간 이내
        - 광범위 토픽은 title_overlap >= 0.25 필요

        Phase 2 — cross-topic 병합 (신규):
        - 같은 국가코드 + 관련 토픽 (conflict↔coup↔terror) 간
        - title 유사도 >= 0.20 AND 6시간 이내
        """
        from collections import defaultdict
        from sqlalchemy import select, text
        from backend.app.models.issue_cluster import IssueCluster
        from worker.processor.trending_engine import _calc_kscore
        from worker.processor.clusterer import _title_similarity
        from worker.processor.trending_engine import _is_junk_title

        _MERGE_TOPICS = {"conflict", "terror", "coup", "diplomacy", "maritime", "protest", "sanctions", "cyber"}
        _BROAD_TOPICS = {"diplomacy", "protest", "maritime", "sanctions", "cyber"}
        # cross-topic 병합 대상: 이 토픽들끼리는 같은 이벤트일 수 있음
        _CROSS_TOPIC_GROUPS = [
            {"conflict", "coup", "terror"},
        ]
        _MAX_EVENTS = 100
        _TIME_WINDOW = timedelta(hours=72)
        _CROSS_TOPIC_WINDOW = timedelta(hours=6)
        _CROSS_TOPIC_SIM = 0.20

        # 활성 + 최근 7일 클러스터만 대상 (전체 로드 시 수천 개 → DB 잠금 + OOM)
        _recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(IssueCluster).where(
                IssueCluster.is_active == True,  # noqa: E712
                IssueCluster.severity > 0,
                IssueCluster.topic.in_(_MERGE_TOPICS),
                IssueCluster.last_event_at >= _recent_cutoff,
            ).order_by(
                IssueCluster.cluster_key,
                IssueCluster.kscore.desc(),
            )
        )
        clusters = result.scalars().all()

        # Phase 1: 같은 cluster_key 병합
        groups: dict[str, list] = defaultdict(list)
        for c in clusters:
            if c.cluster_key and not c.cluster_key.startswith("0000"):
                groups[c.cluster_key].append(c)

        merged_total = 0

        def _do_merge(winner, loser):
            """loser를 winner에 병합하는 공통 로직."""
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
                topic = winner.topic or ""
                if topic in _BROAD_TOPICS:
                    if _title_similarity(winner.title or "", loser.title or "") < 0.25:
                        continue

                _do_merge(winner, loser)
                await db.execute(
                    text("UPDATE cluster_events SET cluster_id = :w WHERE cluster_id = :l"),
                    {"w": winner.id, "l": loser.id},
                )
                loser.severity = 0
                loser.kscore = 0
                merged_total += 1

            age_hours = (datetime.now(timezone.utc) - winner.last_event_at).total_seconds() / 3600 if winner.last_event_at else 0.0
            winner.kscore, _ = _calc_kscore(
                event_count=winner.event_count,
                is_spike=winner.is_spike,
                confidence=winner.confidence,
                severity=winner.severity,
                independent_sources=winner.independent_sources or 1,
                source_tiers=winner.source_tiers or [],
                age_hours=age_hours,
            )
            winner.updated_at = datetime.now(timezone.utc)

        # Phase 2: cross-topic 병합 (같은 국가, 관련 토픽, 유사 제목)
        cross_merged = 0
        # cross-topic 병합 대상 토픽만 필터 (비관련 토픽 early skip으로 O(n) 축소)
        _cross_topic_all = set()
        for grp in _CROSS_TOPIC_GROUPS:
            _cross_topic_all.update(grp)
        # 활성 클러스터 중 cross-topic 대상 토픽만 필터
        active = [c for c in clusters if c.severity > 0 and c.country_code and (c.topic or "") in _cross_topic_all]
        # 국가별 그룹
        by_country: dict[str, list] = defaultdict(list)
        for c in active:
            by_country[c.country_code].append(c)

        _cross_window_secs = _CROSS_TOPIC_WINDOW.total_seconds()
        for cc, cc_clusters in by_country.items():
            if len(cc_clusters) <= 1:
                continue
            # kscore 높은 순 정렬
            cc_clusters.sort(key=lambda x: x.kscore, reverse=True)
            merged_ids: set = set()
            for i, winner in enumerate(cc_clusters):
                if winner.id in merged_ids:
                    continue
                if winner.event_count >= _MAX_EVENTS:
                    continue
                for j in range(i + 1, len(cc_clusters)):
                    loser = cc_clusters[j]
                    if loser.id in merged_ids:
                        continue
                    if winner.event_count >= _MAX_EVENTS:
                        break
                    # 토픽이 같으면 Phase 1에서 이미 처리됨
                    if winner.topic == loser.topic:
                        continue
                    # 관련 토픽 그룹에 속하는지 확인
                    in_same_group = any(
                        (winner.topic or "") in grp and (loser.topic or "") in grp
                        for grp in _CROSS_TOPIC_GROUPS
                    )
                    if not in_same_group:
                        continue
                    # 시간 제한 (비용 낮은 검사를 유사도 전에 수행)
                    if (winner.last_event_at and loser.last_event_at
                            and abs((winner.last_event_at - loser.last_event_at).total_seconds()) > _cross_window_secs):
                        continue
                    # 제목 유사도 체크 (가장 비용 높은 연산이므로 마지막)
                    sim = _title_similarity(
                        winner.title or "", loser.title or "",
                        ko_a=winner.title_ko, ko_b=loser.title_ko,
                    )
                    if sim < _CROSS_TOPIC_SIM:
                        continue

                    logger.info(
                        "Cross-topic 병합: %s(%s) ← %s(%s) sim=%.3f",
                        winner.cluster_key, winner.title[:30],
                        loser.cluster_key, loser.title[:30], sim,
                    )
                    _do_merge(winner, loser)
                    await db.execute(
                        text("UPDATE cluster_events SET cluster_id = :w WHERE cluster_id = :l"),
                        {"w": winner.id, "l": loser.id},
                    )
                    loser.severity = 0
                    loser.kscore = 0
                    merged_ids.add(loser.id)
                    cross_merged += 1

                if winner.id not in merged_ids:
                    age_hours = (datetime.now(timezone.utc) - winner.last_event_at).total_seconds() / 3600 if winner.last_event_at else 0.0
                    winner.kscore, _ = _calc_kscore(
                        event_count=winner.event_count,
                        is_spike=winner.is_spike,
                        confidence=winner.confidence,
                        severity=winner.severity,
                        independent_sources=winner.independent_sources or 1,
                        source_tiers=winner.source_tiers or [],
                        age_hours=age_hours,
                    )
                    winner.updated_at = datetime.now(timezone.utc)

        merged_total += cross_merged
        if merged_total:
            logger.info("분산 클러스터 %d개 병합 완료 (cross-topic: %d)", merged_total, cross_merged)
        return merged_total

    async def _run():
        from worker.processor.trending_engine import calculate_global_trending
        # 병합과 트렌딩 계산을 별도 트랜잭션으로 분리 (장시간 잠금 방지)
        merged = 0
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    merged = await _merge_fragmented_clusters(db)
        except Exception:
            logger.exception("클러스터 병합 실패 (무시, 트렌딩 계산은 계속)")

        async with AsyncSessionLocal() as db:
            async with db.begin():
                results = await calculate_global_trending(db)
                logger.info("트렌딩 계산 완료: %d개 (클러스터 %d개 병합)", len(results), merged)
                return {"status": "ok", "count": len(results), "merged": merged}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("트렌딩 계산 오류: %s", exc)
        raise self.retry(exc=exc)
    finally:
        try:
            r.delete(lock_key)
        except Exception:
            pass


@app.task(
    name="worker.tasks.retry_unprocessed",
    queue="process",
    bind=True,
    max_retries=1,
)
def retry_unprocessed(self):
    """
    미처리 raw_events를 Celery 큐에 재등록 (10분마다).
    워커 재배포 시 큐에서 유실된 태스크를 복구.
    """
    _record_heartbeat("retry_unprocessed")

    async def _run():
        from sqlalchemy import select
        from backend.app.models.raw_event import RawEvent
        from datetime import datetime, timezone, timedelta

        # 큐 과부하 시 배치 축소
        _sync_r = _get_sync_redis()
        queue_len = _sync_r.llen("process")
        if queue_len >= 500:
            logger.info("retry_unprocessed 스킵: process 큐 대기 중 (%d개)", queue_len)
            return {"queued": 0, "skipped_reason": "queue_busy", "queue_len": queue_len}
        # 100~500: 배치 크기 축소하여 계속 처리
        batch_limit = 10 if queue_len >= 100 else 50

        async with AsyncSessionLocal() as db:
            # 재시도 범위 내 미처리 항목만 (그보다 오래된 것은 설계상 포기 —
            # 대신 cleanup_old_data가 보존기간 후 삭제한다. worker/retention.py 참고)
            from worker.retention import UNPROCESSED_RETRY_WINDOW_HOURS

            cutoff = datetime.now(timezone.utc) - timedelta(hours=UNPROCESSED_RETRY_WINDOW_HOURS)
            result = await db.execute(
                select(RawEvent.id)
                .where(
                    RawEvent.processed == False,
                    RawEvent.collected_at >= cutoff,
                )
                # 최신 우선. 피드·SNS 게이트가 "최근 6시간" 신선도를 보므로
                # 백로그를 오래된 것부터 갉으면 아무리 처리해도 화면은 계속 비어 있다.
                # (2026-08-02: 3일치 백로그를 오래된 순으로 처리하다 피드가 빈 채로 방치됨)
                .order_by(RawEvent.collected_at.desc())
                .limit(batch_limit)
            )
            ids = [str(row[0]) for row in result.fetchall()]

        if not ids:
            logger.info("미처리 raw_events 없음 — skip")
            return {"queued": 0}

        for i, raw_id in enumerate(ids):
            process_raw_event.delay(raw_id)
            if (i + 1) % 50 == 0 and i + 1 < len(ids):
                await asyncio.sleep(0.5)
        logger.info("미처리 raw_events %d건 → process_raw_event 큐 등록", len(ids))
        return {"queued": len(ids)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("retry_unprocessed 오류: %s", exc)
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
        from datetime import datetime, timezone, timedelta

        reassigned = 0
        skipped = 0
        zombie_count = 0

        BATCH_SIZE = 500
        MAX_BATCHES = 5  # 무한 루프 방지: 최대 2500개까지만 처리
        seen_ids: set = set()  # 이미 시도한 이벤트 ID 추적

        for batch_num in range(MAX_BATCHES):
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    # cluster_events에 없는 normalized_events (severity>=20, 7일 이내)
                    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                    query = select(NormalizedEvent).where(
                        NormalizedEvent.severity >= 20,
                        NormalizedEvent.event_time >= cutoff,
                        not_(
                            exists().where(
                                ClusterEvent.event_id == NormalizedEvent.id
                            )
                        ),
                    )
                    # 이미 시도한 이벤트 제외 (무한 루프 방지)
                    if seen_ids:
                        query = query.where(NormalizedEvent.id.notin_(seen_ids))
                    query = query.order_by(NormalizedEvent.event_time.asc()).limit(BATCH_SIZE)

                    orphan_result = await db.execute(query)
                    orphans = orphan_result.scalars().all()
                    if not orphans:
                        break
                    logger.info("오펀 이벤트 %d개 배치 처리 시작 (batch %d/%d)", len(orphans), batch_num + 1, MAX_BATCHES)

                    for ev in orphans:
                        seen_ids.add(ev.id)
                        try:
                            cluster, _ = await assign_cluster(ev, db)
                            if cluster:
                                reassigned += 1
                            else:
                                skipped += 1
                        except Exception as e:
                            logger.warning("오펀 재처리 실패 [%s]: %s", ev.id, e)
                            skipped += 1

                    if len(orphans) < BATCH_SIZE:
                        break

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
    name="worker.tasks.process_pending_raw_events",
    queue="process",
    bind=True,
    max_retries=1,
)
def process_pending_raw_events(self):
    """미처리 raw_events 일괄 처리 (워커 시작 시 또는 수동 호출).

    DB에서 processed=false인 raw_events를 배치로 조회하여
    process_raw_event 태스크를 디스패치합니다.
    Disk IO 부하 방지를 위해 배치 사이 딜레이를 둡니다.
    """
    import time

    async def _run():
        from sqlalchemy import select, func
        from backend.app.models.raw_event import RawEvent

        BATCH_SIZE = 500
        MAX_TOTAL = 50000  # 안전 캡
        dispatched = 0

        async with AsyncSessionLocal() as db:
            # 전체 미처리 건수 확인
            cnt_result = await db.execute(
                select(func.count()).select_from(RawEvent).where(RawEvent.processed == False)
            )
            total_pending = cnt_result.scalar() or 0
            logger.info("미처리 raw_events: %d건 (최대 %d건 처리)", total_pending, MAX_TOTAL)

        offset = 0
        while dispatched < MAX_TOTAL:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(RawEvent.id)
                    .where(RawEvent.processed == False)
                    .order_by(RawEvent.collected_at.asc())
                    .offset(offset)
                    .limit(BATCH_SIZE)
                )
                ids = [str(row[0]) for row in result.fetchall()]
                if not ids:
                    break

            # 배치 디스패치 (50개마다 0.5초 지연 → Groq TPM 보호)
            for raw_id in ids:
                process_raw_event.delay(raw_id)
                dispatched += 1
            await asyncio.sleep(1.0)  # 배치 간 1초 대기

            logger.info(
                "process_pending: 배치 디스패치 %d건 (누적 %d/%d)",
                len(ids), dispatched, total_pending,
            )
            offset += BATCH_SIZE

            if len(ids) < BATCH_SIZE:
                break

            # 배치 간 잠시 쉬기 (DB/Redis 부하 분산)
            time.sleep(1)

        logger.info("process_pending 완료: 총 %d건 디스패치", dispatched)
        return {"status": "ok", "dispatched": dispatched, "total_pending": total_pending}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("process_pending_raw_events 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.push_alert",
    queue="process",
    bind=True,
    max_retries=2,
)
def push_alert(self, cluster_id: str, alert_kind: str = "fast"):
    """v7: KScore 기반 통합 알림 발송. alert_kind: 'fast' | 'verified' | 'combined'"""

    async def _run():
        import uuid
        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster
        from worker.push.push_service import send_alert, save_in_app_notifications
        from backend.app.core.redis import get_redis

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(IssueCluster).where(IssueCluster.id == uuid.UUID(cluster_id))
                )
                cluster = result.scalar_one_or_none()
                if not cluster:
                    logger.warning("push_alert: cluster 없음 %s", cluster_id)
                    return {"status": "not_found"}

                redis = get_redis()
                result = await send_alert(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title,
                    country_code=cluster.country_code,
                    severity=cluster.severity,
                    kscore=cluster.kscore,
                    is_verified=cluster.is_verified,
                    cluster_topic=cluster.topic,
                    alert_kind=alert_kind,
                    db=db,
                    redis=redis,
                    cluster_title_ko=cluster.title_ko,
                    signal_corroboration_count=getattr(cluster, "signal_corroboration_count", 0) or 0,
                )

                # 인앱 알림 저장
                notif_type = "verified" if alert_kind == "verified" else "fast"
                await save_in_app_notifications(
                    cluster_id=cluster_id,
                    cluster_title=cluster.title_ko or cluster.title,
                    country_code=cluster.country_code,
                    notif_type=notif_type,
                    db=db,
                    cluster_topic=cluster.topic,
                )

                logger.info("push_alert 완료: kind=%s result=%s", alert_kind, result)
                return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("push_alert 오류 [%s]: %s", cluster_id, exc)
        raise self.retry(exc=exc)


# 하위호환 alias
push_spike_alert = push_alert
push_verified_alert = lambda self_or_id, cluster_id=None: push_alert(
    self_or_id if cluster_id is None else cluster_id, "verified"
)


@app.task(
    name="worker.tasks.flush_alert_digests",
    queue="process",
    bind=True,
    max_retries=1,
)
def flush_alert_digests(self):
    """유저별 다이제스트 버퍼 플러시: 15분마다 pending 알림을 요약 1건으로 묶어 FCM 발송."""

    async def _run():
        from worker.push.push_service import flush_alert_digests as _flush
        from backend.app.core.redis import get_redis

        async with AsyncSessionLocal() as db:
            async with db.begin():
                redis = get_redis()
                result = await _flush(db=db, redis=redis)
                logger.info("flush_alert_digests 완료: %s", result)
                return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("flush_alert_digests 오류: %s", exc)
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
                    # 어드민이 수동 설정한 플랜은 다운그레이드하지 않음
                    if getattr(user, "admin_plan_override", False):
                        continue

                    # 구독 레코드가 아예 없는 경우:
                    # admin_plan_override=True면 수동 부여 → 건드리지 않음 (위에서 이미 처리)
                    # admin_plan_override=False인데 구독 레코드 없음 → 비정상 상태, free로 다운그레이드
                    any_sub_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                        ).limit(1)
                    )
                    if any_sub_result.scalar_one_or_none() is None:
                        # 구독 레코드 없이 유료 플랜 → 비정상, free로 롤백
                        user.plan = "free"
                        from backend.app.services.area_activation import sync_area_activation
                        await sync_area_activation(user.id, "free", db)
                        downgraded += 1
                        logger.info(
                            "expire_subscriptions: 구독 레코드 없는 유료 플랜 유저 다운그레이드 user=%s plan=%s→free",
                            user.id, user.plan,
                        )
                        continue

                    # lifetime 구독이 있으면 만료 체크 건너뜀
                    lifetime_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                            Subscription.status == "active",
                            Subscription.billing_interval == "lifetime",
                        ).limit(1)
                    )
                    if lifetime_result.scalar_one_or_none() is not None:
                        continue

                    # 아직 유효한(expires_at > now) 구독이 있는지 확인
                    # active뿐 아니라 cancelled(만료일까지 유효)·grace_period·billing_retry도 포함
                    sub_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                            Subscription.status.in_(["active", "cancelled", "grace_period", "billing_retry"]),
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
                            # referral Pro가 아직 유효하면 skip
                            if (
                                hasattr(user, "referral_pro_expires_at")
                                and user.referral_pro_expires_at
                                and user.referral_pro_expires_at > now
                            ):
                                continue
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

                # Referral Pro 만료 처리: referral_pro_expires_at <= now
                referral_expired = 0
                referral_result = await db.execute(
                    select(User).where(
                        User.referral_pro_expires_at.isnot(None),
                        User.referral_pro_expires_at <= now,
                        User.plan != "free",
                    )
                )
                for ruser in referral_result.scalars().all():
                    # 유효한 유료 구독이 있으면 건드리지 않음
                    valid_sub_result = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == ruser.id,
                            Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"]),
                            Subscription.expires_at > now,
                        ).limit(1)
                    )
                    if valid_sub_result.scalar_one_or_none() is None:
                        ruser.plan = "free"
                        from backend.app.services.area_activation import sync_area_activation
                        await sync_area_activation(ruser.id, "free", db)
                        referral_expired += 1

                logger.info(
                    "expire_subscriptions: %d명 → free 다운그레이드, trial 만료 %d명, referral 만료 %d명",
                    downgraded, trial_expired, referral_expired,
                )
                return {"status": "ok", "downgraded": downgraded, "trial_expired": trial_expired, "referral_expired": referral_expired}

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
    name="worker.tasks.build_missed_alert_summary",
    queue="process",
    bind=True,
    max_retries=1,
)
def build_missed_alert_summary(self):
    """suppressed(plan_locked/dnd/daily_limit) 기록에서 missed alert 요약 생성. primary 모드만."""

    async def _run():
        from sqlalchemy import select
        from backend.app.models.alert_delivery_log import AlertDeliveryLog
        from backend.app.models.user_missed_spike import UserMissedAlertSummary

        # pipeline_mode='primary'만 집계 (PRD 9)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(AlertDeliveryLog).where(
                        AlertDeliveryLog.decision == "suppressed",
                        AlertDeliveryLog.suppression_reason.in_(["plan_locked", "dnd", "daily_limit"]),
                        AlertDeliveryLog.pipeline_mode == "primary",
                        AlertDeliveryLog.created_at >= cutoff,
                    )
                )
                logs = result.scalars().all()

                created = 0
                for log in logs:
                    # 중복 체크 (cluster_id 기반, spike_event_id 대체)
                    existing = await db.execute(
                        select(UserMissedAlertSummary).where(
                            UserMissedAlertSummary.user_id == log.user_id,
                            UserMissedAlertSummary.alert_cluster_id == log.cluster_id,
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    summary = UserMissedAlertSummary(
                        user_id=log.user_id,
                        cluster_id=log.cluster_id,
                        alert_cluster_id=log.cluster_id,
                        reason=log.suppression_reason,
                    )
                    db.add(summary)
                    created += 1

                logger.info("build_missed_alert: %d건 생성", created)
                return {"created": created}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("build_missed_alert 오류: %s", exc)
        raise self.retry(exc=exc)


# 하위호환 alias
build_missed_spike_summary = build_missed_alert_summary


@app.task(
    name="worker.tasks.reconcile_delivery_logs",
    queue="process",
    bind=True,
    max_retries=1,
)
def reconcile_delivery_logs(self):
    """sent 로그의 토큰 유효성 재확인, missed_alert 보정.

    매일 04:00 UTC 실행.
    - sent인데 해당 유저의 토큰이 모두 expired인 경우 -> failed로 보정
    - suppressed(plan_locked/dnd) 중 missed_alert_summary에 누락된 건 보정
    """

    async def _run():
        from sqlalchemy import select, update as sa_update, and_, exists, not_
        from backend.app.models.alert_delivery_log import AlertDeliveryLog
        from backend.app.models.user_missed_spike import UserMissedAlertSummary
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

                # 2. suppressed(plan_locked/dnd) 중 missed_alert_summary 누락 보정
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
                        select(UserMissedAlertSummary).where(
                            UserMissedAlertSummary.user_id == log.user_id,
                            UserMissedAlertSummary.alert_cluster_id == log.spike_event_id,
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none() is None:
                        summary = UserMissedAlertSummary(
                            user_id=log.user_id,
                            cluster_id=log.cluster_id,
                            alert_cluster_id=log.spike_event_id,
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


async def _send_fcm_to_user(user_id, title: str, body: str, data: dict | None = None):
    """개별 사용자에게 FCM 푸시 발송 (웹+네이티브)."""
    from sqlalchemy import select
    from backend.app.models.user import UserPushToken

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserPushToken).where(
                UserPushToken.user_id == user_id,
                UserPushToken.status == "active",
            ).order_by(UserPushToken.last_seen_at.desc()).limit(1)
        )
        token_row = result.scalar_one_or_none()
        if not token_row:
            return

    from worker.push.push_service import _send_fcm_for_web, _send_fcm_for_native

    fcm_data = data or {}
    if token_row.platform == "web":
        _send_fcm_for_web([token_row.fcm_token], title, body, fcm_data)
    else:
        _send_fcm_for_native([token_row.fcm_token], title, body, fcm_data)


async def _get_user_lang(user_id, db) -> str:
    """사용자 언어 설정 조회. 기본값 ko."""
    from sqlalchemy import select
    from backend.app.models.user import UserPreference

    result = await db.execute(
        select(UserPreference.language).where(UserPreference.user_id == user_id)
    )
    lang = result.scalar_one_or_none()
    return lang if lang in ("ko", "en") else "ko"


async def _send_trial_email(user_email: str, user_name: str, subject: str, template_name: str, template_vars: dict):
    """Trial 관련 이메일 발송 (SMTP)."""
    import smtplib
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import jinja2

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP 미설정 — trial 이메일 발송 건너뜀")
        return

    tpl_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(tpl_dir), autoescape=True)
    try:
        template = env.get_template(template_name)
    except jinja2.TemplateNotFound:
        logger.warning("이메일 템플릿 없음: %s", template_name)
        return

    html_body = template.render(**template_vars)

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        _send_email(user_email, subject, html_body, sender)
    except Exception as e:
        logger.error("trial 이메일 발송 실패: %s → %s", user_email, e)


@app.task(
    name="worker.tasks.send_trial_nudges",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_trial_nudges(self):
    """Trial/Promo D3/D6 넛지 발송. 매일 09:00 UTC (KST 18:00).
    D3: 인앱 + FCM 푸시
    D6: 인앱 + FCM 푸시 + 이메일 (마케팅 동의자만)
    """

    async def _run():
        from sqlalchemy import select, or_
        from sqlalchemy import func
        from backend.app.models.subscription import Subscription
        from backend.app.models.user import User
        from backend.app.models.user_missed_spike import UserMissedAlertSummary
        from backend.app.models.notification import Notification

        now = datetime.now(timezone.utc)
        results = {"d3": 0, "d6": 0, "d6_email": 0}

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # trial + promo 모두 대상 (promo는 started_at 기준)
                # D3 넛지: 시작 72~96시간 경과
                d3_start = now - timedelta(hours=96)
                d3_end = now - timedelta(hours=72)
                d3_subs = await db.execute(
                    select(Subscription).where(
                        or_(
                            Subscription.status == "trial",
                            Subscription.platform.like("promo:%"),
                        ),
                        Subscription.started_at >= d3_start,
                        Subscription.started_at < d3_end,
                        Subscription.status.in_(["trial", "active"]),
                    )
                )
                for sub in d3_subs.scalars().all():
                    lang = await _get_user_lang(sub.user_id, db)

                    # missed alerts 카운트
                    missed_result = await db.execute(
                        select(func.count())
                        .select_from(UserMissedAlertSummary)
                        .where(
                            UserMissedAlertSummary.user_id == sub.user_id,
                            UserMissedAlertSummary.is_shown == False,
                        )
                    )
                    missed_count = missed_result.scalar() or 0

                    if lang == "en":
                        if missed_count > 0:
                            title = f"Pro Trial · Day 3"
                            body = f"{missed_count} alerts detected in the last 72 hours"
                        else:
                            title = "Pro Trial · Day 3"
                            body = "Check the tension level in your monitored regions"
                    else:
                        if missed_count > 0:
                            title = f"Pro 체험 중 · 3일 경과"
                            body = f"지난 72시간 알림 {missed_count}건이 감지되었습니다"
                        else:
                            title = "Pro 체험 중 · 3일 경과"
                            body = "현재 관심 지역의 긴장도를 확인하세요"

                    notif = Notification(
                        user_id=sub.user_id,
                        type="trial_nudge",
                        title=title,
                        body=body,
                    )
                    db.add(notif)

                    # FCM 푸시 발송
                    await _send_fcm_to_user(
                        sub.user_id, title, body,
                        {"type": "trial_nudge", "day": "3"},
                    )
                    results["d3"] += 1

                # D6 넛지: 시작 144~168시간 경과 (만료 1일 전)
                d6_start = now - timedelta(hours=168)
                d6_end = now - timedelta(hours=144)
                d6_subs = await db.execute(
                    select(Subscription).where(
                        or_(
                            Subscription.status == "trial",
                            Subscription.platform.like("promo:%"),
                        ),
                        Subscription.started_at >= d6_start,
                        Subscription.started_at < d6_end,
                        Subscription.status.in_(["trial", "active"]),
                    )
                )
                for sub in d6_subs.scalars().all():
                    lang = await _get_user_lang(sub.user_id, db)

                    # 유저 정보 조회 (이메일, 마케팅 동의)
                    user_result = await db.execute(
                        select(User).where(User.id == sub.user_id)
                    )
                    user = user_result.scalar_one_or_none()

                    # missed alerts 카운트
                    missed_result = await db.execute(
                        select(func.count())
                        .select_from(UserMissedAlertSummary)
                        .where(
                            UserMissedAlertSummary.user_id == sub.user_id,
                            UserMissedAlertSummary.is_shown == False,
                        )
                    )
                    missed_count = missed_result.scalar() or 0

                    if lang == "en":
                        title = "Trial ends tomorrow"
                        body = "Subscribe now to keep all Pro features without interruption."
                        email_subject = "Your WeWantPeace Pro trial ends tomorrow"
                    else:
                        title = "체험 종료 D-1"
                        body = "내일이면 Pro 기능이 비활성화됩니다. 지금 구독하면 끊김 없이 계속 사용할 수 있어요."
                        email_subject = "WeWantPeace Pro 체험이 내일 종료됩니다"

                    notif = Notification(
                        user_id=sub.user_id,
                        type="trial_nudge",
                        title=title,
                        body=body,
                    )
                    db.add(notif)

                    # FCM 푸시 발송
                    await _send_fcm_to_user(
                        sub.user_id, title, body,
                        {"type": "trial_nudge", "day": "6"},
                    )

                    # 이메일 발송 (마케팅 동의 사용자만)
                    if user and user.email and user.marketing_agreed_at:
                        await _send_trial_email(
                            user_email=user.email,
                            user_name=user.display_name or user.nickname or "",
                            subject=email_subject,
                            template_name="trial_expiring.html",
                            template_vars={
                                "user_name": user.display_name or user.nickname or "",
                                "missed_count": missed_count,
                                "lang": lang,
                                "upgrade_url": "https://www.wewantpeace.live/upgrade",
                            },
                        )
                        results["d6_email"] += 1

                    results["d6"] += 1

        logger.info("send_trial_nudges: d3=%d, d6=%d, d6_email=%d",
                     results["d3"], results["d6"], results["d6_email"])
        return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_trial_nudges 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 일일 접속 유도 푸시 (Daily Engagement) ──────────────────────────────────


@app.task(
    name="worker.tasks.send_daily_engagement",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_daily_engagement(self):
    """24시간 미접속 유저에게 관심 국가 기반 개인화 푸시 발송.
    매일 00:00 UTC (09:00 KST).
    """

    async def _run():
        from sqlalchemy import select, func
        from backend.app.models.user import User, UserArea, UserPushToken, UserPreference
        from backend.app.models.tension_index import TensionIndex
        from backend.app.models.issue_cluster import IssueCluster
        from worker.push.push_service import (
            _HOME_COUNTRY_NAMES_KO, _HOME_COUNTRY_NAMES_EN,
            _is_in_quiet_hours,
        )

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        sent = 0
        skipped_quiet = 0
        failed = 0
        total_eligible = 0
        sent_user_ids: list[tuple] = []  # (user_id, tz_name)

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 대상: last_active < 24h, active 토큰 보유 (전체 유저 무조건 발송)
                rows = await db.execute(
                    select(
                        User.id,
                        User.last_active,
                        UserPreference.language,
                        UserPreference.quiet_hours_start,
                        UserPreference.quiet_hours_end,
                        UserPreference.timezone,
                    )
                    .join(UserPreference, UserPreference.user_id == User.id)
                    .join(UserPushToken, UserPushToken.user_id == User.id)
                    .where(
                        User.status == "active",
                        User.last_active < cutoff,
                        UserPushToken.status == "active",
                    )
                    .group_by(
                        User.id,
                        User.last_active,
                        UserPreference.language,
                        UserPreference.quiet_hours_start,
                        UserPreference.quiet_hours_end,
                        UserPreference.timezone,
                    )
                )
                users = rows.all()
                total_eligible = len(users)

                for row in users:
                    user_id = row.id
                    lang = row.language if row.language in ("ko", "en") else "ko"
                    qh_start = row.quiet_hours_start
                    qh_end = row.quiet_hours_end
                    tz_name = row.timezone or "Asia/Seoul"

                    # quiet_hours 체크
                    if qh_start and qh_end:
                        try:
                            from zoneinfo import ZoneInfo
                            now_local = datetime.now(ZoneInfo(tz_name)).time()
                            if _is_in_quiet_hours(now_local, qh_start, qh_end):
                                skipped_quiet += 1
                                continue
                        except Exception as e:
                            logger.warning("engagement quiet_hours 체크 실패 (user=%s, tz=%s): %s", user_id, tz_name, e)

                    # 관심 국가 조회
                    areas_q = await db.execute(
                        select(UserArea.country_code).where(
                            UserArea.user_id == user_id,
                            UserArea.is_active == True,
                            UserArea.country_code.isnot(None),
                        )
                    )
                    country_codes = [r[0] for r in areas_q.all()]

                    if country_codes:
                        # 관심 국가 중 최고 긴장도 조회 (DISTINCT ON 규칙: ORDER BY 첫 컬럼 = DISTINCT 컬럼)
                        tension_q = await db.execute(
                            select(
                                TensionIndex.country_code,
                                TensionIndex.raw_score,
                            )
                            .where(TensionIndex.country_code.in_(country_codes))
                            .order_by(TensionIndex.country_code, TensionIndex.time.desc())
                            .distinct(TensionIndex.country_code)
                        )
                        tensions = tension_q.all()
                        top = max(tensions, key=lambda t: t.raw_score) if tensions else None

                        # 최근 24h 관심 국가 신규 클러스터 수
                        cluster_q = await db.execute(
                            select(func.count())
                            .select_from(IssueCluster)
                            .where(
                                IssueCluster.country_code.in_(country_codes),
                                IssueCluster.created_at >= cutoff,
                                IssueCluster.is_active == True,
                            )
                        )
                        new_issues = cluster_q.scalar() or 0

                        if top:
                            cc = top.country_code
                            score = int(top.raw_score)
                            names_ko = _HOME_COUNTRY_NAMES_KO
                            names_en = _HOME_COUNTRY_NAMES_EN
                            name = names_ko.get(cc, cc) if lang == "ko" else names_en.get(cc, cc)

                            if lang == "ko":
                                title = "오늘의 관심 국가 브리핑"
                                if new_issues > 0:
                                    body = f"{name} 긴장도 {score}점 · 어제 새 이슈 {new_issues}건 감지"
                                else:
                                    body = f"{name} 긴장도 {score}점 · 최신 상황을 확인하세요"
                            else:
                                title = "Your daily briefing"
                                if new_issues > 0:
                                    body = f"{name} tension {score}/100 · {new_issues} new issue(s) detected"
                                else:
                                    body = f"{name} tension {score}/100 · Check the latest updates"
                        else:
                            if lang == "ko":
                                title = "오늘의 글로벌 분쟁 상황"
                                body = "관심 국가의 최신 상황을 확인해보세요"
                            else:
                                title = "Today's global conflicts"
                                body = "Check the latest updates in your watched regions"
                    else:
                        if lang == "ko":
                            title = "오늘의 글로벌 분쟁 상황"
                            body = "전 세계 분쟁 상황을 확인해보세요"
                        else:
                            title = "Today's global conflicts"
                            body = "Check today's worldwide conflict updates"

                    try:
                        await _send_fcm_to_user(
                            user_id, title, body,
                            {"type": "engagement", "action": "open_home"},
                        )
                        sent += 1
                        sent_user_ids.append((user_id, tz_name))
                    except Exception as e:
                        logger.warning("engagement FCM 발송 실패 (user=%s): %s", user_id, e)
                        failed += 1

        # 일일 푸시 카운터에 실제 발송 성공 유저만 반영
        if sent_user_ids:
            try:
                from backend.app.core.redis import get_redis
                redis = get_redis()
                from worker.push.push_service import _increment_daily_push
                for uid, tz in sent_user_ids:
                    await _increment_daily_push(str(uid), redis, tz_name=tz)
            except Exception as e:
                logger.warning("engagement 일일 카운터 증가 실패: %s", e)

        logger.info("send_daily_engagement: sent=%d, failed=%d, skipped_quiet=%d, total_eligible=%d",
                     sent, failed, skipped_quiet, total_eligible)
        return {"sent": sent, "failed": failed, "skipped_quiet": skipped_quiet}

    try:
        _record_heartbeat("send_daily_engagement")
        return run_async(_run())
    except Exception as exc:
        logger.error("send_daily_engagement 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 만료 후 전환 오퍼 발송 ────────────────────────────────────────────────


@app.task(
    name="worker.tasks.send_expired_trial_offers",
    queue="process",
    bind=True,
    max_retries=1,
)
def send_expired_trial_offers(self):
    """만료 후 D+1 할인 오퍼 + D+3 놓친 이슈 리마인더. 매일 10:00 UTC (KST 19:00)."""

    async def _run():
        from sqlalchemy import select, or_, and_
        from sqlalchemy import func
        from backend.app.models.subscription import Subscription
        from backend.app.models.user import User
        from backend.app.models.user_missed_spike import UserMissedAlertSummary
        from backend.app.models.notification import Notification

        now = datetime.now(timezone.utc)
        results = {"d1_push": 0, "d1_email": 0, "d3_email": 0}

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # D+1: 어제 만료된 trial/promo
                yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                yesterday_end = yesterday_start + timedelta(days=1)

                d1_subs = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "expired",
                        or_(
                            Subscription.platform == "trial",
                            Subscription.platform.like("promo:%"),
                        ),
                        Subscription.expires_at >= yesterday_start,
                        Subscription.expires_at < yesterday_end,
                    )
                )

                for sub in d1_subs.scalars().all():
                    lang = await _get_user_lang(sub.user_id, db)
                    user_result = await db.execute(
                        select(User).where(User.id == sub.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if not user:
                        continue

                    # 이미 재구독한 유저 제외
                    active_sub = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == sub.user_id,
                            Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"]),
                        ).limit(1)
                    )
                    if active_sub.scalar_one_or_none():
                        continue

                    # missed alerts
                    missed_result = await db.execute(
                        select(func.count())
                        .select_from(UserMissedAlertSummary)
                        .where(UserMissedAlertSummary.user_id == sub.user_id)
                    )
                    missed_count = missed_result.scalar() or 0

                    if lang == "en":
                        title = "30% off your first month · Get Pro back"
                        body = "Subscribe now and get back real-time alerts and all Pro features."
                        email_subject = "Special offer from WeWantPeace"
                    else:
                        title = "첫 달 30% 할인 · Pro를 다시 만나보세요"
                        body = "지금 구독하면 실시간 알림과 모든 Pro 기능을 다시 사용할 수 있어요."
                        email_subject = "WeWantPeace에서 특별 혜택을 드립니다"

                    # 인앱 알림
                    notif = Notification(
                        user_id=sub.user_id,
                        type="expired_offer",
                        title=title,
                        body=body,
                    )
                    db.add(notif)

                    # FCM 푸시
                    await _send_fcm_to_user(
                        sub.user_id, title, body,
                        {"type": "expired_offer", "action": "upgrade"},
                    )
                    results["d1_push"] += 1

                    # 이메일
                    if user.email and user.marketing_agreed_at:
                        await _send_trial_email(
                            user_email=user.email,
                            user_name=user.display_name or user.nickname or "",
                            subject=email_subject,
                            template_name="trial_expired_offer.html",
                            template_vars={
                                "user_name": user.display_name or user.nickname or "",
                                "missed_count": missed_count,
                                "days_left": 7,
                                "top_issues": [],
                                "lang": lang,
                                "upgrade_url": "https://www.wewantpeace.live/upgrade",
                            },
                        )
                        results["d1_email"] += 1

                # D+3: 3일 전 만료 + 아직 재구독 안 한 유저 → 이메일만
                d3_start = (now - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
                d3_end = d3_start + timedelta(days=1)

                d3_subs = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "expired",
                        or_(
                            Subscription.platform == "trial",
                            Subscription.platform.like("promo:%"),
                        ),
                        Subscription.expires_at >= d3_start,
                        Subscription.expires_at < d3_end,
                    )
                )

                for sub in d3_subs.scalars().all():
                    user_result = await db.execute(
                        select(User).where(User.id == sub.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if not user or not user.email or not user.marketing_agreed_at:
                        continue

                    # 이미 재구독한 유저 제외
                    active_sub = await db.execute(
                        select(Subscription).where(
                            Subscription.user_id == sub.user_id,
                            Subscription.status.in_(["active", "trial", "grace_period", "billing_retry"]),
                        ).limit(1)
                    )
                    if active_sub.scalar_one_or_none():
                        continue

                    lang = await _get_user_lang(sub.user_id, db)

                    missed_result = await db.execute(
                        select(func.count())
                        .select_from(UserMissedAlertSummary)
                        .where(UserMissedAlertSummary.user_id == sub.user_id)
                    )
                    missed_count = missed_result.scalar() or 0

                    if lang == "en":
                        email_subject = f"You've missed {missed_count} crisis alerts since your trial ended"
                    else:
                        email_subject = f"체험 이후 {missed_count}건의 위기 알림을 놓치셨습니다"

                    await _send_trial_email(
                        user_email=user.email,
                        user_name=user.display_name or user.nickname or "",
                        subject=email_subject,
                        template_name="trial_expired_offer.html",
                        template_vars={
                            "user_name": user.display_name or user.nickname or "",
                            "missed_count": missed_count,
                            "days_left": 4,
                            "top_issues": [],
                            "lang": lang,
                            "upgrade_url": "https://www.wewantpeace.live/upgrade",
                        },
                    )
                    results["d3_email"] += 1

        logger.info(
            "send_expired_trial_offers: d1_push=%d, d1_email=%d, d3_email=%d",
            results["d1_push"], results["d1_email"], results["d3_email"],
        )
        return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_expired_trial_offers 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 주간 리포트 PDF 생성 ─────────────────────────────────────────────────


@app.task(
    name="worker.tasks.generate_weekly_pdf",
    queue="process",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def generate_weekly_pdf(self):
    """주간 리포트 PDF 생성 → Supabase 업로드."""
    async def _run():
        from sqlalchemy import text
        from worker.report.pdf_generator import build_pdf, WeeklyReportData
        from worker.report.pdf_uploader import upload_pdf

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            # 이벤트 수
            r = await db.execute(text(
                "SELECT COUNT(*) FROM normalized_events"
                " WHERE event_time >= :cutoff AND is_duplicate = FALSE"
            ), {"cutoff": cutoff})
            total_events = r.scalar() or 0

            # 신규 클러스터
            r = await db.execute(text(
                "SELECT COUNT(*) FROM issue_clusters"
                " WHERE first_seen >= :cutoff AND is_active = TRUE"
            ), {"cutoff": cutoff})
            new_clusters = r.scalar() or 0

            # 위기 국가 (severity >= 60)
            r = await db.execute(text(
                "SELECT COUNT(DISTINCT country_code) FROM issue_clusters"
                " WHERE is_active = TRUE AND severity >= 60"
            ))
            crisis_countries = r.scalar() or 0

            # TOP 10 이슈
            r = await db.execute(text(
                "SELECT title, title_ko, country_code, severity, topic"
                " FROM issue_clusters"
                " WHERE is_active = TRUE AND severity > 0"
                " ORDER BY severity DESC, kscore DESC"
                " LIMIT 10"
            ))
            top_issues = [
                {"title": row[0], "title_ko": row[1], "country_code": row[2],
                 "severity": row[3], "topic": row[4]}
                for row in r.fetchall()
            ]

            # 긴장도 추이 (상위 5개국)
            r = await db.execute(text(
                "SELECT country_code, calculated_at, raw_score"
                " FROM tension_indices"
                " WHERE calculated_at >= :cutoff"
                " AND country_code IN ("
                "   SELECT country_code FROM tension_indices"
                "   WHERE calculated_at >= :cutoff"
                "   GROUP BY country_code"
                "   ORDER BY MAX(raw_score) DESC"
                "   LIMIT 5"
                " )"
                " ORDER BY calculated_at"
            ), {"cutoff": cutoff})
            tension_series = [
                {"country_code": row[0], "time": row[1], "raw_score": row[2]}
                for row in r.fetchall()
            ]

            # 토픽별 분포
            r = await db.execute(text(
                "SELECT topic, COUNT(*) cnt FROM normalized_events"
                " WHERE event_time >= :cutoff AND is_duplicate = FALSE"
                "   AND topic IS NOT NULL AND topic != 'unknown'"
                " GROUP BY topic ORDER BY cnt DESC LIMIT 8"
            ), {"cutoff": cutoff})
            topic_distribution = {row[0]: row[1] for row in r.fetchall()}

        data = WeeklyReportData(
            week_start=cutoff,
            week_end=now,
            total_events=total_events,
            new_clusters=new_clusters,
            crisis_countries=crisis_countries,
            top_issues=top_issues,
            tension_series=tension_series,
            topic_distribution=topic_distribution,
            lang="ko",
        )

        pdf_buffer = build_pdf(data)
        week_label = now.strftime("%Y-W%V")
        filename = f"reports/{week_label}.pdf"
        url = upload_pdf(pdf_buffer.read(), filename)

        logger.info("generate_weekly_pdf 완료: url=%s", url)
        return {"url": url, "week": week_label}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_weekly_pdf 오류: %s", exc)
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

    async with AsyncSessionLocal() as db:
      for batch_start in range(0, len(all_users), batch_size):
        batch = all_users[batch_start:batch_start + batch_size]

        for user in batch:
            try:
                is_pro = user.plan in ("pro", "pro_plus")
                lang = "ko"

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
                _send_email(user.email, subject, html_body, sender)

                sent_total += 1

            except Exception as e:
                logger.warning(
                    "send_weekly_report: 발송 실패 [user=%s, email=%s]: %s",
                    user.id, user.email, e,
                )
                failed_total += 1

        # 배치 간 딜레이 (마지막 배치 제외)
        if batch_start + batch_size < len(all_users):
            import asyncio as _asyncio
            await _asyncio.sleep(0.5)

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
        for admin in admins:
            try:
                _send_email(admin.email, f"[WeWantPeace] KPI Alert — Week of {week_start}", html, sender)
            except Exception as e:
                logger.warning("KPI alert 이메일 발송 실패 [%s]: %s", admin.email, e)

        logger.info("KPI alert 이메일 발송 완료: %d명 admin", len(admins))
    except Exception as e:
        logger.error("KPI alert 이메일 발송 실패: %s", e)


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

        async with AsyncSessionLocal() as db:
            async with db.begin():
                post = await generate_daily_movers(db)
                if not post:
                    return {"status": "skipped"}

            logger.info("generate_daily_social: 자동 승인 생성 완료 post=%s", post.id)
            return {"status": "ok", "post_id": str(post.id)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_daily_social 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.generate_kscore_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def generate_kscore_social(self):
    """v7: KScore >= 5.0 클러스터에 대한 SNS 포스트 생성 (SpikeEvent 테이블 조회 제거)."""

    async def _run():
        from worker.social.config import SOCIAL_AUTOGEN_ENABLED
        from worker.processor.calibration import KSCORE_SOCIAL_MIN
        if not SOCIAL_AUTOGEN_ENABLED:
            return {"status": "disabled"}

        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster
        from backend.app.models.social_post import SocialPost
        from worker.social.generators import generate_kscore_alert

        created = 0

        async with AsyncSessionLocal() as db:
            async with db.begin():
                cutoff = datetime.now(timezone.utc) - timedelta(hours=6)

                # 최근 72시간 내 생성되었거나 발행된 클러스터 제외 (중복 방지)
                dedup_cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
                existing_ids_result = await db.execute(
                    select(SocialPost.source_cluster_id)
                    .where(
                        SocialPost.content_type == "kscore_alert",
                        SocialPost.created_at >= dedup_cutoff,
                    )
                )
                already_posted = {r[0] for r in existing_ids_result.fetchall() if r[0] is not None}
                # published 상태 포스트는 72시간 내 published_at 기준으로도 체크
                published_ids_result = await db.execute(
                    select(SocialPost.source_cluster_id)
                    .where(
                        SocialPost.content_type == "kscore_alert",
                        SocialPost.status == "published",
                        SocialPost.published_at >= dedup_cutoff,
                    )
                )
                already_posted |= {r[0] for r in published_ids_result.fetchall() if r[0] is not None}

                query = (
                    select(IssueCluster)
                    .where(
                        IssueCluster.kscore >= KSCORE_SOCIAL_MIN,
                        IssueCluster.severity >= 60,
                        IssueCluster.is_active == True,
                        IssueCluster.last_event_at >= cutoff,
                    )
                    .order_by(IssueCluster.kscore.desc())
                    .limit(10)
                )
                if already_posted:
                    query = query.where(IssueCluster.id.notin_(already_posted))
                result = await db.execute(query)
                clusters = result.scalars().all()

                posts_to_notify = []
                for cluster in clusters:
                    post = await generate_kscore_alert(cluster, db)
                    if post:
                        posts_to_notify.append(post)
                        created += 1

            # 자동 발행 모드: 리뷰 건너뛰고 즉시 approved 상태로 생성됨
            # publish_approved_social 태스크가 2분 내 픽업하여 발행
            if posts_to_notify:
                logger.info("generate_kscore_social: %d건 자동 승인 생성 완료", len(posts_to_notify))

        return {"status": "ok", "created": created}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("generate_kscore_social 오류: %s", exc)
        raise self.retry(exc=exc)


# 하위호환 alias
generate_spike_social = generate_kscore_social


@app.task(
    name="worker.tasks.test_playwright",
    queue="process",
    bind=True,
)
def test_playwright(self):
    """Playwright 동작 여부 즉시 진단용 태스크 (운영 데이터 불변)."""
    import traceback as _tb
    result = {}
    try:
        from worker.social.card_html_generator import generate_html_card
        data = generate_html_card(
            content_type="kscore_alert",
            issues=[{
                "title_en": "Playwright Test Card",
                "title_ko": "플레이라이트 테스트 카드",
                "country_code": "UA",
                "severity": 85,
                "independent_sources": 1,
                "source_tiers": [],
                "is_verified": False,
                "event_count": 1,
            }],
            date="2026.05.19",
        )
        if data:
            result = {"status": "ok", "size_bytes": len(data)}
            logger.warning("PLAYWRIGHT_TEST OK: %d bytes", len(data))
        else:
            result = {"status": "failed", "reason": "generate_html_card returned None"}
            logger.warning("PLAYWRIGHT_TEST FAILED: returned None")
    except Exception:
        tb = _tb.format_exc()
        result = {"status": "error", "traceback": tb}
        logger.warning("PLAYWRIGHT_TEST ERROR: %s", tb)
    return result


@app.task(
    name="worker.tasks.test_card_real",
    queue="process",
    bind=True,
)
def test_card_real(self):
    """실제 DB 클러스터로 HTML 카드 생성 검증 (운영 데이터 불변, 업로드 없음)."""
    import traceback as _tb

    async def _run():
        from sqlalchemy import select
        from backend.app.models.issue_cluster import IssueCluster

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(IssueCluster)
                .where(IssueCluster.is_active == True, IssueCluster.severity >= 60)
                .order_by(IssueCluster.kscore.desc())
                .limit(1)
            )
            cluster = result.scalar_one_or_none()

        if not cluster:
            return {"status": "no_cluster"}

        issues = [{
            "title_en": cluster.title or "",
            "title_ko": cluster.title_ko or cluster.title or "",
            "country_code": cluster.country_code or "",
            "severity": cluster.severity or 0,
            "independent_sources": getattr(cluster, "independent_sources", 0),
            "source_tiers": getattr(cluster, "source_tiers", []) or [],
            "is_verified": getattr(cluster, "is_verified", False),
            "event_count": getattr(cluster, "event_count", 0),
        }]
        bg_image_url = getattr(cluster, "image_url", None)

        import asyncio, functools
        from worker.social.card_html_generator import generate_html_card
        # sync_playwright는 asyncio 루프 안에서 직접 호출 불가 → run_in_executor
        fn = functools.partial(
            generate_html_card,
            content_type="kscore_alert",
            issues=issues,
            date=None,
            image_url=bg_image_url,
        )
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fn)
        if data:
            return {
                "status": "ok",
                "size_bytes": len(data),
                "cluster_id": str(cluster.id),
                "country": cluster.country_code,
                "severity": cluster.severity,
                "has_bg_image": bool(bg_image_url),
            }
        return {"status": "failed", "reason": "generate_html_card returned None"}

    try:
        result = run_async(_run())
        logger.warning("CARD_REAL_TEST: %s", result)
        return result
    except Exception:
        tb = _tb.format_exc()
        logger.warning("CARD_REAL_TEST ERROR: %s", tb)
        return {"status": "error", "traceback": tb}


@app.task(
    name="worker.tasks.force_html_card_post",
    queue="process",
    bind=True,
)
def force_html_card_post(self):
    """HTML 카드 즉시 확인용: 상위 클러스터의 dedup 제거 후 새 포스트 강제 생성."""
    import traceback as _tb

    async def _run():
        from sqlalchemy import select, delete
        from backend.app.models.issue_cluster import IssueCluster
        from backend.app.models.social_post import SocialPost
        from worker.social.generators import generate_kscore_alert

        # ① 클러스터 조회
        cluster_id = None
        async with AsyncSessionLocal() as db:
            async with db.begin():
                r = await db.execute(
                    select(IssueCluster)
                    .where(IssueCluster.is_active == True, IssueCluster.severity >= 70)
                    .order_by(IssueCluster.kscore.desc())
                    .limit(1)
                )
                cluster = r.scalar_one_or_none()
            if not cluster:
                return {"status": "no_cluster"}
            cluster_id = cluster.id
            country = cluster.country_code
            severity = cluster.severity
            logger.warning(
                "force_html_card_post: cluster=%s country=%s sev=%d",
                cluster_id, country, severity,
            )

        # ② 기존 dedup 포스트 삭제 (세션 분리)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dedup_key = f"kscore_alert:{cluster_id}:{today}"
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(
                    delete(SocialPost).where(
                        SocialPost.source_cluster_id == cluster_id,
                        SocialPost.content_type == "kscore_alert",
                        SocialPost.status.in_(["draft", "approved", "pending"]),
                    )
                )
                await db.execute(
                    delete(SocialPost).where(SocialPost.dedup_key == dedup_key)
                )

        # ③ 새 포스트 생성 (HTML 카드 포함, 세션 분리)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 클러스터 재조회 (새 세션)
                r2 = await db.execute(
                    select(IssueCluster).where(IssueCluster.id == cluster_id)
                )
                cluster = r2.scalar_one_or_none()
                if not cluster:
                    return {"status": "cluster_not_found"}
                post = await generate_kscore_alert(cluster, db)

        if not post:
            return {"status": "still_blocked", "cluster_id": str(cluster_id)}

        return {
            "status": "ok",
            "post_id": str(post.id),
            "image_url": post.image_url,
            "cluster_id": str(cluster_id),
            "country": country,
            "severity": severity,
        }

    try:
        result = run_async(_run())
        logger.warning("FORCE_HTML_CARD: %s", result)
        return result
    except Exception:
        tb = _tb.format_exc()
        logger.warning("FORCE_HTML_CARD ERROR: %s", tb[:500])
        return {"status": "error", "traceback": tb}


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

        async with AsyncSessionLocal() as db:
            async with db.begin():
                post = await generate_weekly_recap(db)
                if not post:
                    return {"status": "skipped"}

            logger.info("generate_weekly_social: 자동 승인 생성 완료 post=%s", post.id)
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
    linkedin_enabled: bool = False,
    telegram_channel_enabled: bool = False,
) -> bool:
    """단일 포스트를 X/Threads/Instagram/LinkedIn/Telegram 채널에 발행. 하나라도 성공하면 True."""
    from sqlalchemy import select
    from backend.app.models.social_post import SocialPostPlatform

    any_ok = False  # 하나라도 성공하면 True

    # 이미지 업로드: card_generator에서 즉시 업로드됨 (로컬 경로 폴백 처리)
    if post.image_url and not post.image_url.startswith(("http://", "https://")):
        from worker.social.image_uploader import upload_image, is_configured
        if is_configured():
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
            if platform_id:
                any_ok = True
        elif x_record.status == "published":
            any_ok = True

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
            if platform_id:
                any_ok = True
        elif th_record.status == "published":
            any_ok = True

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
            if platform_id:
                any_ok = True
        elif ig_record.status == "published":
            any_ok = True

    # LinkedIn
    if linkedin_enabled:
        existing_li = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == "linkedin",
            )
        )
        li_record = existing_li.scalar_one_or_none()

        if not li_record:
            from worker.social.adapters.linkedin_adapter import publish as li_publish
            platform_id, error = li_publish(post)
            li_record = SocialPostPlatform(
                post_id=post.id,
                platform="linkedin",
                platform_post_id=platform_id,
                status="published" if platform_id else "failed",
                error_message=error,
                published_at=datetime.now(timezone.utc) if platform_id else None,
            )
            db.add(li_record)
            if platform_id:
                any_ok = True
        elif li_record.status == "published":
            any_ok = True

    # Telegram Channel (Broadcast)
    if telegram_channel_enabled:
        existing_tg = await db.execute(
            select(SocialPostPlatform).where(
                SocialPostPlatform.post_id == post.id,
                SocialPostPlatform.platform == "telegram_channel",
            )
        )
        tg_record = existing_tg.scalar_one_or_none()

        if not tg_record:
            from worker.social.adapters.telegram_channel_adapter import publish as tg_publish
            platform_id, error = tg_publish(post)
            tg_record = SocialPostPlatform(
                post_id=post.id,
                platform="telegram_channel",
                platform_post_id=platform_id,
                status="published" if platform_id else "failed",
                error_message=error,
                published_at=datetime.now(timezone.utc) if platform_id else None,
            )
            db.add(tg_record)
            if platform_id:
                any_ok = True
        elif tg_record.status == "published":
            any_ok = True

    return any_ok


@app.task(
    name="worker.tasks.publish_approved_social",
    queue="process",
    bind=True,
    max_retries=1,
)
def publish_approved_social(self):
    """approved 상태 포스트를 X/Threads/Instagram/LinkedIn/Telegram 채널에 발행."""

    async def _run():
        from sqlalchemy import select
        from backend.app.models.social_post import SocialPost
        from worker.social.config import (
            SOCIAL_PLATFORM_X_ENABLED,
            SOCIAL_PLATFORM_THREADS_ENABLED,
            SOCIAL_PLATFORM_INSTAGRAM_ENABLED,
            SOCIAL_PLATFORM_LINKEDIN_ENABLED,
            SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED,
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
                        SOCIAL_PLATFORM_LINKEDIN_ENABLED,
                        SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED,
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
            # Telegram 리포트 전송
            from worker.social.telegram_bot import send_publish_report
            await send_publish_report(posts, published, failed)
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
    name="worker.tasks.send_daily_metrics_to_bosskit",
    queue="process",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def send_daily_metrics_to_bosskit(self):
    """Bosskit 지표 대시보드에 사업 지표 일일 전송.

    /admin/bot-stats(도핑봇 전용)·compute_funnel_metrics와 동일한 정의를
    그대로 재사용한다 — 이 값들은 이미 여러 곳에서 검증된 기준이라
    새로 정의를 만들면 어드민 화면 숫자와 어긋날 위험이 있다.
    """
    import os
    import httpx

    BOSSKIT_INGEST_URL = (
        "https://api.bosskit.me/metric-sources/"
        "2349e3f8-8e9f-4e2f-a122-bb8964aa024b/"
        "aa6e109b-e09a-4a22-9657-20c75548fd3c/ingest"
    )

    async def _run():
        from sqlalchemy import select, func
        from backend.app.models.subscription import Subscription, PaymentHistory
        from backend.app.models.user import User, UserPushToken
        from backend.app.models.community import Feedback
        from backend.app.routers.admin import (
            _active_not_expired, _IS_PROMO_SUB, _today_start_kst, _kst_boundary, KST, _dau_query,
        )
        from backend.app.services.funnel import compute_funnel_metrics

        now = datetime.now(timezone.utc)
        today_start = _today_start_kst()
        month_start = _kst_boundary(
            datetime.now(KST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        )

        async with AsyncSessionLocal() as db:
            total_users = (await db.execute(
                select(func.count()).select_from(User).where(User.status != "deleted")
            )).scalar() or 0
            new_today = (await db.execute(
                select(func.count()).select_from(User)
                .where(User.created_at >= today_start, User.status != "deleted")
            )).scalar() or 0
            dau = (await db.execute(_dau_query(today_start))).scalar() or 0
            subscribers = (await db.execute(
                select(func.count()).select_from(Subscription)
                .where(_active_not_expired(now), ~_IS_PROMO_SUB)
            )).scalar() or 0
            promo_subscribers = (await db.execute(
                select(func.count()).select_from(Subscription)
                .where(_active_not_expired(now), _IS_PROMO_SUB)
            )).scalar() or 0
            monthly_revenue = (await db.execute(
                select(func.coalesce(func.sum(PaymentHistory.amount), 0))
                .where(PaymentHistory.status == "success", PaymentHistory.created_at >= month_start)
            )).scalar() or 0
            push_tokens = (await db.execute(
                select(func.count()).select_from(UserPushToken)
            )).scalar() or 0
            feedback_count = (await db.execute(
                select(func.count()).select_from(Feedback)
            )).scalar() or 0

            funnel = await compute_funnel_metrics(db, now)

        subscribers = int(subscribers)
        monthly_revenue = int(monthly_revenue)
        arpu = round(monthly_revenue / subscribers, 0) if subscribers else 0

        metrics = {
            "전체 가입자": int(total_users),
            "오늘 신규가입": int(new_today),
            "일일 활성 사용자": int(dau),
            "유료 구독자": subscribers,
            "프로모 구독자": int(promo_subscribers),
            "이번달 매출": monthly_revenue,
            "구독자당 월매출": int(arpu),
            "푸시 수신 가능 사용자": int(push_tokens),
            "누적 피드백": int(feedback_count),
            "활성화율": funnel["activation_rate"],
            "유료전환율": funnel["conversion_rate"],
            "1일 리텐션": funnel["retention_d1"],
            "7일 리텐션": funnel["retention_d7"],
            "30일 리텐션": funnel["retention_d30"],
        }

        key = os.environ.get("BOSSKIT_METRIC_INGEST_KEY", "")
        if not key:
            logger.warning("send_daily_metrics_to_bosskit: BOSSKIT_METRIC_INGEST_KEY 미설정 — 전송 스킵")
            return {"status": "skipped", "reason": "no_key", "metrics": metrics}

        # 인증 방식 미확정 — 배포 전 Bearer/X-API-Key/쿼리파라미터 등 여러 방식을
        # 실제로 테스트했으나 전부 동일한 401을 반환해 스킴을 특정하지 못했다.
        # 정확한 방식 확인 전까지는 실패해도 로그로만 남기고 태스크 자체는
        # 재시도만 하도록 둔다(raise_for_status가 예외를 던지면 self.retry로 감).
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                BOSSKIT_INGEST_URL,
                json={"metrics": metrics},
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code >= 400:
                logger.error(
                    "send_daily_metrics_to_bosskit: 전송 실패 HTTP %d — %s",
                    resp.status_code, resp.text[:300],
                )
                resp.raise_for_status()

        logger.info("send_daily_metrics_to_bosskit: 전송 완료 %s", metrics)
        return {"status": "ok", "metrics": metrics}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("send_daily_metrics_to_bosskit 오류: %s", exc)
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
            lines = [
                f"<b>소스 신뢰도 주간 보고</b>",
                f"{week_ago.date()} ~ {now.date()}",
                "",
                f"대표님, 금주 소스채널 신뢰도 분석 결과를 보고 드립니다.",
                "",
            ]

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

            lines.append("")
            lines.append("이상 보고 드립니다.")
            lines.append("<i>WeWantPeace 시스템 비서</i>")
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

    72시간 이상 이벤트 미추가 + severity < 30 → is_active=False.
    severity 30 미만만 비활성화 (30-49 범위의 진행 중 분쟁은 보호).
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
                    IssueCluster.severity < 30,  # 50→30: 심각도 30-49 분쟁 클러스터 보호
                )
            )
            target_count = count_q.scalar() or 0

            if target_count > 0:
                await db.execute(
                    update(IssueCluster)
                    .where(
                        IssueCluster.is_active == True,  # noqa: E712
                        IssueCluster.last_event_at < stale_cutoff,
                        IssueCluster.severity < 30,  # 50→30
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


# ── 대형 클러스터 분할 ─────────────────────────────────────────────────────


@app.task(
    name="worker.tasks.split_oversized_clusters",
    queue="process",
    bind=True,
    max_retries=1,
)
def split_oversized_clusters_task(self):
    """대형 클러스터 sub_topic 기반 자동 분할 (6시간마다)."""

    async def _run():
        from worker.processor.clusterer import split_oversized_clusters
        async with AsyncSessionLocal() as db:
            splits = await split_oversized_clusters(db)
            await db.commit()
            return {"status": "ok", "splits": len(splits)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("split_oversized_clusters 오류: %s", exc)
        raise self.retry(exc=exc)


# ── SNS 토큰 자동 갱신 ─────────────────────────────────────────────────────


@app.task(
    name="worker.tasks.refresh_social_tokens",
    queue="process",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5분 후 재시도
)
def refresh_social_tokens(self):
    """SNS 플랫폼 토큰 자동 갱신 (주 1회).

    현재 지원: Threads (60일 만료 토큰 갱신).
    향후 확장: Instagram, LinkedIn 등.
    """

    async def _run():
        from worker.social.token_refresh import refresh_threads_token

        results = {}

        # Threads 토큰 갱신
        threads_result = await refresh_threads_token()
        results["threads"] = threads_result
        logger.info(
            "Threads 토큰 갱신 결과: status=%s, detail=%s",
            threads_result["status"],
            threads_result["detail"],
        )

        # 향후 다른 플랫폼 토큰 갱신 추가 가능:
        # results["instagram"] = await refresh_instagram_token()
        # results["linkedin"] = await refresh_linkedin_token()

        return results

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("refresh_social_tokens 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 비활성 RSS 피드 자동 복구 ─────────────────────────────────────────────────


@app.task(
    name="worker.tasks.recheck_inactive_feeds",
    queue="collect",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def recheck_inactive_feeds(self):
    """비활성화된 RSS 피드를 HTTP HEAD로 재확인, 200 OK면 자동 복구 (매일 06:00 UTC)."""

    async def _run():
        import httpx
        from sqlalchemy import select
        from backend.app.models.source_channel import SourceChannel
        from backend.app.core.redis import get_redis

        redis = get_redis()
        recovered = []
        checked = 0

        async with AsyncSessionLocal() as db:
            # is_active=False인 RSS 피드만 조회
            stmt = select(SourceChannel).where(
                SourceChannel.is_active == False,  # noqa: E712
                SourceChannel.source_type == "rss",
                SourceChannel.feed_url.isnot(None),
            )
            result = await db.execute(stmt)
            inactive_feeds = list(result.scalars().all())

            if not inactive_feeds:
                logger.info("recheck_inactive_feeds: 비활성 RSS 피드 없음")
                return {"checked": 0, "recovered": 0, "feeds": []}

            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WeWantPeace/1.0)"},
            ) as client:
                for feed in inactive_feeds:
                    checked += 1
                    try:
                        resp = await client.head(feed.feed_url)
                        if resp.status_code == 200:
                            # 복구: is_active=True로 변경
                            feed.is_active = True
                            db.add(feed)

                            # Redis 에러 카운트 리셋
                            if redis is not None:
                                try:
                                    await redis.delete(f"rss:consecutive_errors:{feed.id}")
                                    await redis.delete(f"rss:not_found:{feed.id}")
                                except Exception:
                                    logger.debug("Redis 에러 카운트 리셋 실패 (feed=%s)", feed.id, exc_info=True)

                            recovered.append(feed.display_name)
                            logger.info(
                                "RSS 피드 자동 복구: %s (%s) — HTTP %d",
                                feed.display_name, feed.feed_url, resp.status_code,
                            )
                        else:
                            logger.debug(
                                "RSS 피드 여전히 비활성: %s — HTTP %d",
                                feed.display_name, resp.status_code,
                            )
                    except Exception as e:
                        logger.debug(
                            "RSS 피드 재확인 실패: %s — %s",
                            feed.display_name, e,
                        )

            if recovered:
                await db.commit()

        logger.info(
            "recheck_inactive_feeds 완료: %d개 확인, %d개 복구 — %s",
            checked, len(recovered), ", ".join(recovered) if recovered else "없음",
        )
        return {
            "checked": checked,
            "recovered": len(recovered),
            "feeds": recovered,
        }

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("recheck_inactive_feeds 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 시스템 헬스체크 + 자동수정 ────────────────────────────────────────────────


@app.task(
    name="worker.tasks.health_check",
    queue="process",
    bind=True,
    max_retries=1,
)
def health_check(self):
    """6시간마다 시스템 건강 체크 → 텔레그램 리포트 전송."""

    async def _run():
        from worker.health.checker import run_all_checks
        from worker.health.notifier import send_health_report

        results = await run_all_checks()
        await send_health_report(results)

        ok_count = sum(1 for r in results if r.status == "ok")
        issue_count = sum(len(r.issues) for r in results)
        return {
            "status": "ok",
            "checks": len(results),
            "healthy": ok_count,
            "issues": issue_count,
        }

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("health_check 오류: %s", exc)
        raise self.retry(exc=exc)


# process_health_approvals 제거됨 (2026-03-10)
# telegram_bot.py _poll_updates()가 hfix:/hskip: 콜백을 직접 처리하므로
# 독립 getUpdates polling이 불필요하며 409 Conflict만 유발함


# ── Intelligence Layers: 시그널 수집 + 교차검증 ──────────────────────────────

@app.task(
    name="worker.tasks.collect_firms",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def collect_firms(self):
    """NASA FIRMS 위성 열점 수집 (15분마다)."""
    _record_heartbeat("collect_firms")

    async def _run():
        from worker.collector.firms_collector import FIRMSCollector
        async with AsyncSessionLocal() as db:
            collector = FIRMSCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.commit()
                logger.info("FIRMS 수집 완료: 총 %d개 저장", total)
            else:
                logger.info("FIRMS 수집 완료: 새 열점 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("FIRMS 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_outage",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def collect_outage(self):
    """IODA 인터넷 단절 수집 (15분마다)."""
    _record_heartbeat("collect_outage")

    async def _run():
        from worker.collector.outage_collector import OutageCollector
        async with AsyncSessionLocal() as db:
            collector = OutageCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.commit()
                logger.info("IODA 수집 완료: 총 %d개 저장", total)
            else:
                logger.info("IODA 수집 완료: 새 단절 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("IODA 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_cloudflare_radar",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def collect_cloudflare_radar(self):
    """Cloudflare Radar 트래픽 이상 수집 (30분마다)."""
    _record_heartbeat("collect_cloudflare_radar")

    async def _run():
        from worker.collector.cloudflare_radar_collector import CloudflareRadarCollector
        async with AsyncSessionLocal() as db:
            collector = CloudflareRadarCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.commit()
                logger.info("Cloudflare Radar 수집 완료: 총 %d개 저장", total)
            else:
                logger.info("Cloudflare Radar 수집 완료: 새 이상 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("Cloudflare Radar 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_gps_jam",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def collect_gps_jam(self):
    """GPS 교란 탐지 수집 (15분마다)."""
    _record_heartbeat("collect_gps_jam")

    async def _run():
        from worker.collector.gps_jam_collector import GpsJamCollector
        async with AsyncSessionLocal() as db:
            collector = GpsJamCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.commit()
                logger.info("GPS 교란 수집 완료: 총 %d개 저장", total)
            else:
                logger.info("GPS 교란 수집 완료: 감지 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("GPS 교란 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.collect_ucdp",
    queue="collect",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def collect_ucdp(self):
    """UCDP 역사적 분쟁 데이터 수집 (매일 06:00 UTC)."""
    _record_heartbeat("collect_ucdp")

    async def _run():
        from worker.collector.ucdp_collector import UCDPCollector
        async with AsyncSessionLocal() as db:
            collector = UCDPCollector()
            results = await collector.collect_all(db)
            total = sum(r.collected for r in results)
            if total > 0:
                await db.flush()
                all_ids = []
                for r in results:
                    for raw_ev in r.raw_event_ids:
                        if raw_ev.id:
                            all_ids.append(str(raw_ev.id))
                await db.commit()
                for i, raw_id in enumerate(all_ids):
                    process_raw_event.delay(raw_id)
                    if (i + 1) % 50 == 0 and i + 1 < len(all_ids):
                        await asyncio.sleep(0.5)
                logger.info("UCDP 수집 완료: 총 %d개 → process_raw_event %d개 트리거", total, len(all_ids))
            else:
                logger.info("UCDP 수집 완료: 새 이벤트 없음")
            return {"total_collected": total}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("UCDP 수집 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.correlate_signals",
    queue="process",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def correlate_signals(self):
    """시그널 ↔ 이슈 클러스터 교차검증 (5분마다)."""
    _record_heartbeat("correlate_signals")

    async def _run():
        from worker.processor.signal_correlator import correlate_signals as _correlate
        async with AsyncSessionLocal() as db:
            result = await _correlate(db)
            await db.commit()
            return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("시그널 교차검증 오류: %s", exc)
        raise self.retry(exc=exc)


@app.task(
    name="worker.tasks.cleanup_expired_signals",
    queue="process",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def cleanup_expired_signals(self):
    """만료된 시그널 정리 (6시간마다)."""
    _record_heartbeat("cleanup_expired_signals")

    async def _run():
        from worker.processor.signal_correlator import cleanup_expired_signals as _cleanup
        async with AsyncSessionLocal() as db:
            count = await _cleanup(db)
            await db.commit()
            return {"deleted": count}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("시그널 정리 오류: %s", exc)
        raise self.retry(exc=exc)


# ── Beat heartbeat ────────────────────────────────────────────────────────────

@app.task(name="beat_heartbeat")
def beat_heartbeat():
    """Beat 프로세스가 살아있음을 표시."""
    r = _get_sync_redis()
    r.set("beat:heartbeat", datetime.now(UTC).isoformat(), ex=600)


# ── 오래된 데이터 하드 삭제 ───────────────────────────────────────────────────

@app.task(
    name="worker.tasks.cleanup_old_data",
    queue="process",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def cleanup_old_data(self):
    """
    오래된 데이터 배치 삭제 (Disk IO 폭발 방지).
    매일 새벽 3시 30분 UTC 실행.
    """
    _record_heartbeat("cleanup_old_data")

    async def _run():
        from sqlalchemy import text as sa_text

        BATCH_SIZE = 5000
        results = {"raw_events": 0, "noise_normalized": 0, "tension_index": 0}

        async with AsyncSessionLocal() as db:
            # 1. 보존기간 지난 raw_events 배치 삭제 (Disk IO 방지)
            #
            # 예전에는 processed = true 만 지웠다. 그런데 retry_unprocessed는
            # 최근 6시간 내 미처리 건만 재시도하므로, 그 범위를 벗어난 미처리 건은
            # 재시도도 삭제도 되지 않고 영구히 남아 "백로그 과다" 경보를 계속
            # 발생시켰다 (실측: 2026-06-07부터 5,547건 적체).
            # 보존기간이 지난 건은 어차피 처리되지 않으므로 processed 여부와
            # 무관하게 삭제한다. (worker/retention.py 참고)
            from worker.retention import RAW_EVENT_RETENTION_DAYS

            cutoff_raw = datetime.now(timezone.utc) - timedelta(days=RAW_EVENT_RETENTION_DAYS)
            while True:
                async with db.begin():
                    r = await db.execute(
                        sa_text(
                            "DELETE FROM raw_events WHERE ctid IN "
                            "(SELECT ctid FROM raw_events "
                            "WHERE collected_at < :cutoff LIMIT :batch)"
                        ),
                        {"cutoff": cutoff_raw, "batch": BATCH_SIZE},
                    )
                    if r.rowcount == 0:
                        break
                    results["raw_events"] += r.rowcount

            # 2. severity=0 normalized_events 배치 삭제
            while True:
                async with db.begin():
                    r = await db.execute(
                        sa_text(
                            "DELETE FROM normalized_events WHERE ctid IN "
                            "(SELECT ctid FROM normalized_events WHERE severity = 0 LIMIT :batch)"
                        ),
                        {"batch": BATCH_SIZE},
                    )
                    if r.rowcount == 0:
                        break
                    results["noise_normalized"] += r.rowcount

            # 3. 90일+ tension_index 배치 삭제 (Pro+ 플랜 90일 히스토리 지원)
            cutoff_tension = datetime.now(timezone.utc) - timedelta(days=90)
            while True:
                async with db.begin():
                    r = await db.execute(
                        sa_text(
                            "DELETE FROM tension_index WHERE ctid IN "
                            "(SELECT ctid FROM tension_index WHERE time < :cutoff LIMIT :batch)"
                        ),
                        {"cutoff": cutoff_tension, "batch": BATCH_SIZE},
                    )
                    if r.rowcount == 0:
                        break
                    results["tension_index"] += r.rowcount

            logger.info(
                "cleanup_old_data: raw_events=%d, noise_norm=%d, tension=%d 삭제",
                results["raw_events"], results["noise_normalized"], results["tension_index"],
            )
            return {"status": "ok", **results}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("cleanup_old_data 오류: %s", exc)
        raise self.retry(exc=exc)


# ── 뉴스레터 초안 자동 생성 ──────────────────────────────────────────────────
@app.task(
    bind=True,
    name="worker.tasks.generate_newsletter_draft",
    queue="process",
    max_retries=1,
    default_retry_delay=120,
)
def generate_newsletter_draft(self):
    """월요일 자동 뉴스레터 초안 생성 (KR + EN)."""
    import subprocess
    import sys

    _record_heartbeat("generate_newsletter_draft")

    import redis as sync_redis
    r = sync_redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )

    # 현재 최대 vol 번호: latest_draft_vol 기반 (키 스캔 대신 안정적)
    # 원자적 INCR로 vol 번호 할당 (동시 실행 시 중복 방지)
    next_vol = r.incr("newsletter:latest_draft_vol")
    logger.info("newsletter draft: allocated vol=%d", next_vol)

    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "scripts",
        "generate_newsletter_data.py",
    )

    results = {}
    for lang in ["kr", "us"]:
        try:
            result = subprocess.run(
                [sys.executable, script_path, "--vol", str(next_vol), "--lang", lang],
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ},
            )
            logger.info(
                "newsletter draft %s: exit=%d", lang, result.returncode
            )
            if result.returncode != 0:
                logger.error(
                    "newsletter draft %s failed: %s",
                    lang,
                    result.stderr[:500],
                )
            results[lang] = {
                "exit_code": result.returncode,
                "stdout": result.stdout[-200:] if result.stdout else "",
            }
        except Exception as e:
            logger.error("newsletter draft %s error: %s", lang, e)
            results[lang] = {"error": str(e)}

    # 성공 여부 확인 (INCR로 이미 할당됨 — 실패 시에도 vol은 소비됨)
    any_success = any(
        res.get("exit_code") == 0 for res in results.values() if "exit_code" in res
    )
    if any_success:
        logger.info("newsletter draft vol=%d saved to Redis", next_vol)
    else:
        logger.error("newsletter draft 전부 실패, vol 번호 미업데이트")

    return {"status": "ok" if any_success else "all_failed", "vol": next_vol, "results": results}


# ── 뉴스레터 시간대별 자동 발송 ────────────────────────────────────────────────
@app.task(
    bind=True,
    name="worker.tasks.send_newsletter_scheduled",
    queue="process",
    max_retries=1,
    default_retry_delay=120,
)
def send_newsletter_scheduled(self, tz_group: str):
    """시간대 그룹별 뉴스레터 자동 발송.

    tz_group: "asia", "europe", "americas"
    """
    _record_heartbeat("send_newsletter_scheduled")

    TIMEZONE_GROUPS = {
        "asia": [
            "Asia/Seoul", "Asia/Tokyo", "Asia/Shanghai", "Asia/Hong_Kong",
            "Asia/Singapore", "Asia/Taipei", "Asia/Kolkata", "Asia/Bangkok",
            "Australia/Sydney", "Pacific/Auckland",
        ],
        "europe": [
            "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Rome",
            "Europe/Madrid", "Europe/Moscow", "Europe/Istanbul", "Europe/Warsaw",
            "Africa/Cairo", "Africa/Lagos", "Africa/Johannesburg",
        ],
        "americas": [
            "America/New_York", "America/Chicago", "America/Denver",
            "America/Los_Angeles", "America/Sao_Paulo", "America/Mexico_City",
            "America/Toronto", "America/Buenos_Aires",
        ],
    }

    allowed_tz = TIMEZONE_GROUPS.get(tz_group, [])
    if not allowed_tz:
        logger.warning(f"Unknown tz_group: {tz_group}")
        return {"error": f"Unknown tz_group: {tz_group}"}

    async def _send():
        from backend.app.core.config import settings
        from backend.app.core.redis import get_redis
        from backend.app.models.user import User, UserPreference
        from sqlalchemy import select
        import chevron
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import hmac as _hmac
        from hashlib import sha256 as _sha256
        import json

        redis = get_redis()

        # 자동 발송 토글 확인 (기본값: ON)
        auto_send = await redis.get("newsletter:auto_send")
        if auto_send == "0":
            logger.info(f"Auto-send disabled (tz_group={tz_group})")
            return {"status": "auto_send_disabled"}

        # 최신 draft vol 번호 가져오기
        vol_match = await redis.get("newsletter:latest_draft_vol")
        if not vol_match:
            logger.info(f"No draft vol available (tz_group={tz_group})")
            return {"status": "no_draft_ready"}

        # Get draft data from Redis
        draft_kr_raw = await redis.get(f"admin:newsletter:draft:vol{vol_match}-kr")
        draft_en_raw = await redis.get(f"admin:newsletter:draft:vol{vol_match}-us")

        if not draft_kr_raw and not draft_en_raw:
            logger.warning(f"Draft not found for vol {vol_match}")
            return {"status": "draft_not_found"}

        draft_kr = json.loads(draft_kr_raw) if draft_kr_raw else None
        draft_en = json.loads(draft_en_raw) if draft_en_raw else None

        # Load templates
        from pathlib import Path
        tpl_dir = Path(__file__).parent.parent / "backend" / "app" / "templates" / "newsletter"

        tpl_kr = None
        tpl_en = None
        kr_path = tpl_dir / "newsletter-v1-final-ko.html"
        en_path = tpl_dir / "newsletter-v1-final-en.html"
        if kr_path.exists():
            tpl_kr = kr_path.read_text(encoding="utf-8")
        if en_path.exists():
            tpl_en = en_path.read_text(encoding="utf-8")

        resend_key = os.environ.get("RESEND_API_KEY")
        if not resend_key and (not settings.smtp_user or not settings.smtp_password):
            logger.error("Neither RESEND_API_KEY nor SMTP configured, skipping newsletter send")
            return {"status": "smtp_not_configured"}

        async with AsyncSessionLocal() as db:
            # Get users with marketing consent
            result = await db.execute(
                select(User, UserPreference).join(
                    UserPreference, User.id == UserPreference.user_id, isouter=True
                ).where(
                    User.marketing_agreed_at != None,
                    User.status != "deleted",
                    User.email != None,
                )
            )
            rows = result.all()

            # Filter by timezone group
            users_to_send = []
            for user, pref in rows:
                user_tz = pref.timezone if pref else "Asia/Seoul"
                if user_tz in allowed_tz:
                    user_lang = pref.language if pref else "ko"
                    users_to_send.append((user, user_lang))

            if not users_to_send:
                logger.info(f"No users in tz_group={tz_group}")
                return {"status": "no_users", "tz_group": tz_group}

            sent = 0
            failed = 0
            for user, user_lang in users_to_send:
                try:
                    if user_lang == "en" and tpl_en and draft_en:
                        template = tpl_en
                        data = draft_en
                    elif tpl_kr and draft_kr:
                        template = tpl_kr
                        data = draft_kr
                    else:
                        continue

                    token = _hmac.new(settings.secret_key.encode(), str(user.id).encode(), _sha256).hexdigest()[:32]
                    # apex(wewantpeace.live)는 DNS 레코드가 없어 열리지 않는다 — 반드시 www를 쓸 것.
                    user_data = {**data, "unsubscribe_url": f"https://www.wewantpeace.live/unsubscribe?token={token}"}
                    html = chevron.render(template, user_data)

                    vol = data.get("vol_number", "?")
                    subject = f"WeWantPeace Newsletter Vol.{vol}"

                    _send_email(user.email, subject, html)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Failed to send to {user.email}: {e}")
                    failed += 1

            # MarketingEmailLog 저장 (자동 발송 이력)
            try:
                from backend.app.models.community import MarketingEmailLog
                vol = draft_kr.get("vol_number") if draft_kr else (draft_en.get("vol_number") if draft_en else "?")
                log = MarketingEmailLog(
                    admin_id=None,
                    subject=f"WeWantPeace Newsletter Vol.{vol} (auto/{tz_group})",
                    body=f"자동 발송: tz_group={tz_group}, sent={sent}, failed={failed}",
                    sent_count=sent,
                    failed_count=failed,
                    status="completed" if sent > 0 else "failed",
                )
                db.add(log)
                await db.commit()
                logger.info("MarketingEmailLog 저장 완료: vol=%s, sent=%d, failed=%d", vol, sent, failed)
            except Exception as log_err:
                logger.error("MarketingEmailLog 저장 실패: %s", log_err)
                try:
                    await db.rollback()
                except Exception:
                    pass

        logger.info(f"Newsletter sent: tz_group={tz_group}, sent={sent}, failed={failed}")
        return {"status": "ok", "tz_group": tz_group, "sent": sent, "failed": failed}

    return run_async(_send())
