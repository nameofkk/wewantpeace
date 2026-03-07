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

# 스파이크 알림 최소 severity
SPIKE_SOCIAL_SEVERITY_MIN = int(os.getenv("SPIKE_SOCIAL_SEVERITY_MIN", "60"))
