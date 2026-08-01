from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    env: str = "local"
    database_url: str = "postgresql+asyncpg://resume:resume@localhost:5432/resume_builder"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production-min-32-chars-long"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    cors_origins: str = "http://localhost:8000"
    s3_endpoint: str | None = None
    s3_bucket: str = "resume-builder"
    s3_prefix: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str = ""
    xai_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""
    app_version: str = "dev"
    deployed_at: str = ""
    deploy_env: str = "local"
    run_unlock_price_usd: float = 3.99
    support_url: str = ""
    public_base_url: str = "http://localhost:8000"
    auth_login_url: str = "https://5432wire.com/login"
    auth_return_allowlist: str = "https://resumebild.5432wire.com,http://localhost:8000"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cognito_region: str = "us-east-1"
    # Empty string = auto-derive from configured payment providers.
    payments_enabled_override: str = Field(default="", alias="PAYMENTS_ENABLED")

    @property
    def payments_enabled(self) -> bool:
        override = self.payments_enabled_override.strip().lower()
        if override in ("true", "1", "yes"):
            return True
        if override in ("false", "0", "no"):
            return False
        stripe_ok = bool((self.stripe_secret_key or "").strip())
        crypto_ok = bool((self.nowpayments_api_key or "").strip())
        return stripe_ok or crypto_ok

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.env not in ("local", "test")

    @property
    def cognito_enabled(self) -> bool:
        return bool(
            (self.cognito_user_pool_id or "").strip() and (self.cognito_app_client_id or "").strip()
        )

    @property
    def auth_return_allowlist_hosts(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.auth_return_allowlist.split(",") if o.strip()]

    def s3_object_key(self, key: str) -> str:
        prefix = (self.s3_prefix or "").strip().strip("/")
        clean = key.lstrip("/")
        if not prefix:
            return clean
        return f"{prefix}/{clean}"


settings = Settings()
