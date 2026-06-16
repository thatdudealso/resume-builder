from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    database_url: str = "postgresql+asyncpg://resume:resume@localhost:5432/resume_builder"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production-min-32-chars-long"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    cors_origins: str = "http://localhost:8000"
    s3_endpoint: str | None = None
    s3_bucket: str = "resume-builder"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    hf_token: str = ""
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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.env not in ("local", "test")


settings = Settings()
