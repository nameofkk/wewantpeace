from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, worker_process_init
import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "wewantpeace",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 재시도 설정
    task_max_retries=3,
    task_default_retry_delay=60,
    # Celery 6.0 deprecation warning 제거
    broker_connection_retry_on_startup=True,
)

app.conf.beat_schedule = {
    "collect-telegram": {
        "task": "worker.tasks.collect_telegram",
        "schedule": crontab(minute="*/5"),  # 5분마다 (채널 12개 대응)
        "options": {"queue": "collect"},
    },
    "collect-rss": {
        "task": "worker.tasks.collect_rss",
        "schedule": crontab(minute="*/5"),  # 5분마다
        "options": {"queue": "collect"},
    },
    # ── API 소스 수집 (소스 확장 Phase 3) ──
    "collect-gdelt": {
        "task": "worker.tasks.collect_gdelt",
        "schedule": crontab(minute="*/15"),  # 15분마다
        "options": {"queue": "collect"},
    },
    "collect-acled": {
        "task": "worker.tasks.collect_acled",
        "schedule": crontab(minute=30, hour=6),  # 매일 06:30 UTC
        "options": {"queue": "collect"},
    },
    "collect-reliefweb": {
        "task": "worker.tasks.collect_reliefweb",
        "schedule": crontab(minute="*/30"),  # 30분마다
        "options": {"queue": "collect"},
    },
    "collect-usgs": {
        "task": "worker.tasks.collect_usgs",
        "schedule": crontab(minute="*/5"),  # 5분마다 (M5.0+ 지진)
        "options": {"queue": "collect"},
    },
    "collect-travel-advisory": {
        "task": "worker.tasks.collect_travel_advisory",
        "schedule": crontab(minute=0, hour="*/6"),  # 6시간마다
        "options": {"queue": "collect"},
    },
    "calc-tension": {
        "task": "worker.tasks.calculate_tension",
        "schedule": crontab(minute="1,6,11,16,21,26,31,36,41,46,51,56"),  # 5분마다 (+1분 오프셋)
        "options": {"queue": "process"},
    },
    "calc-trending": {
        "task": "worker.tasks.calculate_trending",
        "schedule": crontab(minute="2,7,12,17,22,27,32,37,42,47,52,57"),  # 5분마다 (+2분 오프셋)
        "options": {"queue": "process"},
    },
    "reprocess-orphans": {
        "task": "worker.tasks.reprocess_orphans",
        "schedule": crontab(minute=0, hour="*/1"),  # 1시간마다
        "options": {"queue": "process"},
    },
    "expire-subscriptions": {
        "task": "worker.tasks.expire_subscriptions",
        "schedule": crontab(minute=0, hour=2),  # 매일 새벽 2시 UTC
        "options": {"queue": "process"},
    },
    "sync-store-subscriptions": {
        "task": "worker.tasks.sync_store_subscriptions",
        "schedule": crontab(minute=0, hour="*/4"),  # 4시간마다
        "options": {"queue": "process"},
    },
    "cleanup-stale-tokens": {
        "task": "worker.tasks.cleanup_stale_tokens",
        "schedule": crontab(minute=0, hour=3),  # 매일 새벽 3시 UTC
        "options": {"queue": "process"},
    },
    # ── Sprint 2: Delivery Integrity 배치 ──
    "timeout-pending-deliveries": {
        "task": "worker.tasks.timeout_pending_deliveries",
        "schedule": crontab(minute="*/10"),  # 매 10분
        "options": {"queue": "process"},
    },
    "build-missed-spike-summary": {
        "task": "worker.tasks.build_missed_spike_summary",
        "schedule": crontab(minute="*/30"),  # 매 30분
        "options": {"queue": "process"},
    },
    "reconcile-delivery-logs": {
        "task": "worker.tasks.reconcile_delivery_logs",
        "schedule": crontab(minute=0, hour=4),  # 매일 04:00 UTC
        "options": {"queue": "process"},
    },
    # ── Sprint 3: Trial 넛지 ──
    "send-trial-nudges": {
        "task": "worker.tasks.send_trial_nudges",
        "schedule": crontab(minute=0, hour=9),  # 매일 09:00 UTC = KST 18:00
        "options": {"queue": "process"},
    },
    # ── 만료 후 전환 오퍼 ──
    "send-expired-trial-offers": {
        "task": "worker.tasks.send_expired_trial_offers",
        "schedule": crontab(minute=0, hour=10),  # 매일 10:00 UTC = KST 19:00
        "options": {"queue": "process"},
    },
    # ── 주간 리포트 ──
    "send-weekly-report": {
        "task": "worker.tasks.send_weekly_report",
        "schedule": crontab(minute=0, hour=9, day_of_week=1),  # 매주 월요일 09:00 UTC = KST 18:00
        "options": {"queue": "process"},
    },
    # ── Admin Ops v0.9 ──
    "snapshot-weekly-kpi": {
        "task": "worker.tasks.snapshot_weekly_kpi",
        "schedule": crontab(minute=5, hour=15, day_of_week=0),  # Sun 15:05 UTC = Mon 00:05 KST
        "options": {"queue": "process"},
    },
    "aggregate-link-clicks": {
        "task": "worker.tasks.aggregate_link_clicks",
        "schedule": crontab(minute=0, hour="*/1"),  # 매 1시간
        "options": {"queue": "process"},
    },
    # ── SNS 자동 포스팅 ──
    "generate-daily-social": {
        "task": "worker.tasks.generate_daily_social",
        "schedule": crontab(minute=0, hour=0),  # 매일 00:00 UTC = KST 09:00
        "options": {"queue": "process"},
    },
    "generate-spike-social": {
        "task": "worker.tasks.generate_spike_social",
        "schedule": crontab(minute="*/10"),  # 10분마다 (부하 분산)
        "options": {"queue": "process"},
    },
    "generate-weekly-social": {
        "task": "worker.tasks.generate_weekly_social",
        "schedule": crontab(minute=0, hour=0, day_of_week=1),  # 매주 월요일
        "options": {"queue": "process"},
    },
    "publish-approved-social": {
        "task": "worker.tasks.publish_approved_social",
        "schedule": crontab(minute="*/2"),  # 2분마다 approved 상태 게시물 발행
        "options": {"queue": "process"},
    },
    # ── SNS 운영 리포트 ──
    "send-daily-social-report": {
        "task": "worker.tasks.send_daily_social_report",
        "schedule": crontab(minute=0, hour=23),  # 매일 23:00 UTC = KST 08:00
        "options": {"queue": "process"},
    },
    "send-weekly-social-report": {
        "task": "worker.tasks.send_weekly_social_report",
        "schedule": crontab(minute=0, hour=23, day_of_week=0),  # 매주 일요일 23:00 UTC
        "options": {"queue": "process"},
    },
    # ── 서비스 모니터링 ──
    "monitor-service-health": {
        "task": "worker.tasks.monitor_service_health",
        "schedule": crontab(minute="3,8,13,18,23,28,33,38,43,48,53,58"),  # 5분마다 (+3분 오프셋)
        "options": {"queue": "process"},
    },
    # ── P1 파이프라인 품질 ──
    "evaluate-source-reliability": {
        "task": "worker.tasks.evaluate_source_reliability",
        "schedule": crontab(minute=30, hour=15, day_of_week=0),  # Sun 15:30 UTC = Mon 00:30 KST
        "options": {"queue": "process"},
    },
    "detect-severity-outliers": {
        "task": "worker.tasks.detect_severity_outliers",
        "schedule": crontab(minute=0, hour=5),  # 매일 05:00 UTC = KST 14:00
        "options": {"queue": "process"},
    },
    "deactivate-stale-clusters": {
        "task": "worker.tasks.deactivate_stale_clusters",
        "schedule": crontab(minute=0, hour=6),  # 매일 06:00 UTC = KST 15:00
        "options": {"queue": "process"},
    },
    # ── SNS 토큰 자동 갱신 ──
    "refresh-social-tokens": {
        "task": "worker.tasks.refresh_social_tokens",
        "schedule": crontab(minute=0, hour=12, day_of_week=3),  # 매주 수요일 12:00 UTC = KST 21:00
        "options": {"queue": "process"},
    },
    # ── Phase 1 마케팅 체크리스트 ──
    "send-daily-checklist": {
        "task": "worker.tasks.send_daily_checklist",
        "schedule": crontab(minute=0, hour=0),  # UTC 00:00 = KST 09:00
        "options": {"queue": "process"},
    },
    # ── 비활성 RSS 피드 자동 복구 ──
    "recheck-inactive-feeds": {
        "task": "worker.tasks.recheck_inactive_feeds",
        "schedule": crontab(minute=0, hour=6),  # 매일 06:00 UTC
        "options": {"queue": "collect"},
    },
}


@worker_process_init.connect
def on_worker_process_init(**kwargs):
    """각 ForkPoolWorker 프로세스 시작 시 Firebase 초기화.

    prefork 모드에서 worker_ready는 MainProcess에서만 실행되고
    fork된 자식 프로세스(ForkPoolWorker)에는 Firebase SDK가 전달되지 않음.
    worker_process_init은 각 자식 프로세스마다 호출됨.
    """
    from backend.app.core.firebase_init import init_firebase
    init_firebase()


@worker_ready.connect
def on_worker_ready(**kwargs):
    """워커 시작 시 긴장도·트렌딩 즉시 계산 + Telegram 봇 시작."""
    app.send_task("worker.tasks.calculate_tension", queue="process")
    app.send_task("worker.tasks.calculate_trending", queue="process")

    # SNS Telegram 봇 polling 시작
    try:
        from worker.social.telegram_bot import start_polling_loop
        start_polling_loop()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Telegram 봇 시작 실패 (무시): %s", e)
