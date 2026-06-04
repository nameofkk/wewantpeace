"""
Sentry 에러 모니터링 초기화.
SENTRY_DSN 환경변수가 없으면 조용히 비활성화.
"""
import os
import logging

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        logger.info("SENTRY_DSN 미설정 — Sentry 비활성화")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        environment = os.getenv("ENVIRONMENT", "development")
        release = os.getenv("APP_VERSION", "0.1.0")

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0.1,          # 10% 트레이스 샘플링
            profiles_sample_rate=0.05,        # 5% 프로파일링
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.WARNING,    # WARNING 이상 Sentry 전송
                    event_level=logging.ERROR,
                ),
            ],
            # PII 제거
            send_default_pii=False,
            # 민감 헤더 필터
            before_send=_before_send,
        )
        logger.info("Sentry 초기화 완료 (env=%s, release=%s)", environment, release)

    except ImportError:
        logger.warning("sentry-sdk 패키지 없음 — pip install sentry-sdk[fastapi]")


def _before_send(event: dict, hint: dict) -> dict | None:
    """Authorization 헤더, 비밀번호 필드 제거."""
    request = event.get("request", {})
    headers = request.get("headers", {})
    if "authorization" in headers:
        headers["authorization"] = "[Filtered]"
    if "x-dev-uid" in headers:
        headers["x-dev-uid"] = "[Filtered]"
    return event
