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
        "schedule": crontab(minute="*/3"),  # 3분마다
        "options": {"queue": "collect"},
    },
    "collect-rss": {
        "task": "worker.tasks.collect_rss",
        "schedule": crontab(minute="*/5"),  # 5분마다
        "options": {"queue": "collect"},
    },
    "calc-tension": {
        "task": "worker.tasks.calculate_tension",
        "schedule": crontab(minute="*/5"),  # 5분마다
        "options": {"queue": "process"},
    },
    "calc-trending": {
        "task": "worker.tasks.calculate_trending",
        "schedule": crontab(minute="*/5"),  # 5분마다
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
    """워커 시작 시 긴장도·트렌딩 즉시 계산."""
    app.send_task("worker.tasks.calculate_tension", queue="process")
    app.send_task("worker.tasks.calculate_trending", queue="process")
