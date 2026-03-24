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
    secret_key: str = ""

    @model_validator(mode="after")
    def enforce_secret_key(self) -> "Settings":
        import logging, os, secrets
        _log = logging.getLogger(__name__)
        if not self.secret_key:
            if not self.debug and os.getenv("RAILWAY_ENVIRONMENT"):
                raise ValueError(
                    "SECRET_KEY must be set in production. "
                    "Add SECRET_KEY environment variable in Railway dashboard."
                )
            self.secret_key = secrets.token_hex(32)
            _log.warning(
                "SECRET_KEY not set — generated random key for this session. "
                "Set SECRET_KEY env var before deploying to production!"
            )
        return self

    # 토스 앱인토스 + 프로덕션 도메인은 항상 허용 (환경변수 ALLOWED_ORIGINS와 병합됨)
    extra_cors_origins: List[str] = [
        # 토스 WebView 실제 origin (tossmini.com 도메인)
        "https://wewantpeace.apps.tossmini.com",
        "https://wewantpeace.private-apps.tossmini.com",
        # 토스 콘솔/API 도메인
        "https://apps-in-toss.toss.im",
        "https://apps-in-toss-api.toss.im",
        # 프로덕션 웹
        "https://www.wewantpeace.live",
        "https://wewantpeace.live",
    ]
    # 토스 WebView origin: *.tossmini.com + *.toss.im 모두 허용
    cors_origin_regex: str = r"^https://[a-z0-9-]+\.(tossmini\.com|toss\.im)$"
    allowed_origins: List[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def merge_extra_cors_origins(self) -> "Settings":
        """extra_cors_origins를 allowed_origins에 병합 (중복 제거)."""
        for origin in self.extra_cors_origins:
            if origin not in self.allowed_origins:
                self.allowed_origins.append(origin)
        return self

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

    # Alert pipeline mode (shadow → primary)
    alert_pipeline_mode: str = "shadow"

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

    # 토스 앱인토스 (Toss Apps-in-Toss) — mTLS 인증
    toss_client_cert_b64: str = ""     # mTLS 인증서 (base64, Railway용)
    toss_client_key_b64: str = ""      # mTLS 개인키 (base64, Railway용)
    toss_client_cert_path: str = ""    # mTLS 인증서 파일 경로 (로컬 개발용)
    toss_client_key_path: str = ""     # mTLS 개인키 파일 경로 (로컬 개발용)
    toss_decryption_key: str = ""      # 유저 정보 복호화 키 (AES-256-GCM)
    toss_decryption_aad: str = ""      # 복호화 AAD

    # DodoPayments
    dodo_api_key: str = ""           # DODO_API_KEY
    dodo_webhook_key: str = ""       # DODO_WEBHOOK_KEY
    dodo_product_pro: str = ""       # DodoPayments Pro 월간 상품 ID
    dodo_product_proplus: str = ""   # DodoPayments Pro+ 월간 상품 ID
    dodo_product_pro_annual: str = ""       # DodoPayments Pro 연간 상품 ID
    dodo_product_proplus_annual: str = ""   # DodoPayments Pro+ 연간 상품 ID
    dodo_product_pro_lifetime: str = ""     # DodoPayments Pro Lifetime 상품 ID
    dodo_product_proplus_lifetime: str = "" # DodoPayments Pro+ Lifetime 상품 ID
    dodo_environment: str = "live_mode"  # "test_mode" | "live_mode"

    # SMTP (마케팅 메일링)
    smtp_host: str = "smtp.naver.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()
