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
