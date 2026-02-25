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
    def warn_insecure_defaults(self) -> "Settings":
        import logging
        _log = logging.getLogger(__name__)
        if self.secret_key == "dev-secret-change-me-in-production":
            _log.warning(
                "⚠️  SECRET_KEY is using the default insecure value. "
                "Set SECRET_KEY environment variable before deploying to production!"
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


settings = Settings()
