"""Application settings - reads from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://concierge:concierge@localhost:5432/concierge"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "dev-secret-key-change-in-production"
    widget_token_expire_seconds: int = 1800  # 30 min
    cors_cache_ttl_seconds: int = 60
    vault_token: str = ""
    service_token: str = "dev-service-token"
    classifier_url: str = ""
    guardrails_url: str = "http://guardrails:8011"
    openai_api_key: str = ""
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
