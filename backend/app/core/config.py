from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DB
    database_url: str = "postgresql+asyncpg://wwp:wwplocal@localhost/wewantpeace"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_db_url_scheme(cls, v: str) -> str:
        """Railway는 postgres:// 또는 postgresql:// 형태로 제공 → asyncpg 드라이버로 변환."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session: str = ""

    # Firebase / FCM
    fcm_project_id: str = ""
    google_application_credentials: str = ""

    # 보안
    secret_key: str = "dev-secret-change-me-in-production"

    @model_validator(mode="after")
    def enforce_secret_key(self) -> "Settings":
        import logging, os
        _log = logging.getLogger(__name__)
        if self.secret_key == "dev-secret-change-me-in-production":
            if not self.debug and os.getenv("RAILWAY_ENVIRONMENT"):
                raise ValueError(
                    "SECRET_KEY must be set in production. "
                    "Add SECRET_KEY environment variable in Railway dashboard."
                )
            _log.warning(
                "SECRET_KEY is using the default insecure value. "
                "Set SECRET_KEY env var before deploying to production!"
            )
        return self

    allowed_origins: List[str] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [item.strip() for item in parsed]
                except (json.JSONDecodeError, TypeError):
                    pass
            return [item.strip() for item in v.split(",")]
        return v

    # 앱 설정
    app_name: str = "WeWantPeace API"
    debug: bool = False
    log_level: str = "INFO"
    disable_auth: bool = False
    upload_dir: str = "media/uploads"

    # 수집 설정
    telegram_collect_interval: int = 300   # 5분 (초)
    rss_collect_interval: int = 600        # 10분 (초)
    tension_calc_interval: int = 900       # 15분 (초)
    trending_calc_interval: int = 900      # 15분 (초)

    # Google Play Billing
    google_play_service_account_json: str = ""  # JSON 문자열 (Railway 환경변수)
    google_rtdn_webhook_token: str = ""  # Pub/Sub push URL의 ?token= 파라미터 검증용

    # Apple StoreKit / App Store Server API
    apple_issuer_id: str = ""
    apple_key_id: str = ""
    apple_private_key_path: str = ""
    apple_bundle_id: str = "com.wewantpeace.app"
    apple_environment: str = "Sandbox"  # "Production" when live

    # 토스 앱인토스 (Toss Apps-in-Toss)
    toss_app_secret: str = ""          # 토스 콘솔에서 발급받은 앱 시크릿
    toss_decryption_key: str = ""      # 유저 정보 복호화 키 (AES-256-GCM)
    toss_decryption_aad: str = ""      # 복호화 AAD

    # SMTP (마케팅 메일링)
    smtp_host: str = "smtp.naver.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()
