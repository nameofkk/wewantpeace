"""SNS 자동 포스팅 — Kill Switch 환경변수."""
import os

# 콘텐츠 자동 생성 활성화 여부
SOCIAL_AUTOGEN_ENABLED = os.getenv("SOCIAL_AUTOGEN_ENABLED", "true") == "true"

# low risk 포스트 자동 발행 (14일 의무 승인 기간 후 수동 전환)
SOCIAL_AUTOPUBLISH_LOW_ENABLED = os.getenv("SOCIAL_AUTOPUBLISH_LOW_ENABLED", "false") == "true"

# 플랫폼별 활성화
SOCIAL_PLATFORM_X_ENABLED = os.getenv("SOCIAL_PLATFORM_X_ENABLED", "true") == "true"
SOCIAL_PLATFORM_THREADS_ENABLED = os.getenv("SOCIAL_PLATFORM_THREADS_ENABLED", "false") == "true"
SOCIAL_PLATFORM_INSTAGRAM_ENABLED = os.getenv("SOCIAL_PLATFORM_INSTAGRAM_ENABLED", "false") == "true"
SOCIAL_PLATFORM_LINKEDIN_ENABLED = os.getenv("SOCIAL_PLATFORM_LINKEDIN_ENABLED", "false") == "true"
SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED = os.getenv("SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED", "false") == "true"

# v7: KScore 기반 SNS 포스트 최소 KScore (스파이크 severity 대체)
KSCORE_SOCIAL_MIN = float(os.getenv("KSCORE_SOCIAL_MIN", "5.0"))
# 하위호환
SPIKE_SOCIAL_SEVERITY_MIN = int(os.getenv("SPIKE_SOCIAL_SEVERITY_MIN", "60"))

# Threads 영어 브리프 운영 상한 (2026-09-30 개편)
# 하루 33건씩 자동으로 나가던 속보 알림을 품질 게이트를 통과한 소수로 줄인다.
SOCIAL_ALERTS_PER_DAY = int(os.getenv("SOCIAL_ALERTS_PER_DAY", "4"))
SOCIAL_ALERT_MIN_GAP_HOURS = float(os.getenv("SOCIAL_ALERT_MIN_GAP_HOURS", "2"))
SOCIAL_MIN_SOURCES = int(os.getenv("SOCIAL_MIN_SOURCES", "3"))

# 이 시각(ISO 8601, UTC) 전까지 만든 게시물은 바로 나가지 않고 텔레그램 승인을 거친다.
# 새 형식 첫 이틀은 사람이 보고 내보내기 위한 장치. 비우면 자동 승인.
SOCIAL_REVIEW_UNTIL = os.getenv("SOCIAL_REVIEW_UNTIL", "")


def review_required(now=None) -> bool:
    from datetime import datetime, timezone
    if not SOCIAL_REVIEW_UNTIL:
        return False
    try:
        until = datetime.fromisoformat(SOCIAL_REVIEW_UNTIL.replace("Z", "+00:00"))
    except ValueError:
        return True  # 값이 깨져 있으면 안전하게 승인 쪽으로
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) < until
