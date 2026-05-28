"""Central settings for the API service.

Hanan owns secure environment loading.
Mohammad uses these settings to wire backend services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(slots=True)
class AppSettings:
    """Typed runtime settings for the platform spine."""

    app_env: str = "dev"
    app_name: str = "multi-tenant-ai-concierge"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/concierge"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "http://localhost:9000"
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "change-me"
    widget_issuer: str = "concierge-widget"
    widget_token_ttl_seconds: int = 300
    widget_shared_secret: str = "dev-widget-secret"
    widget_allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: ("http://localhost:3000", "http://localhost:5173")
    )
    tenant_id_header: str = "X-Tenant-Id"
    request_id_header: str = "X-Request-Id"
    actor_role_header: str = "X-Actor-Role"
    actor_subject_header: str = "X-Actor-Subject"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    chat_model: str = "gpt-4.1-mini"
    classifier_model: str = "classifier.onnx"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "concierge-api"

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Build settings from the process environment."""

        gemini_api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        default_chat_model = "gemini-2.0-flash" if gemini_api_key else "gpt-4.1-mini"

        return cls(
            app_env=os.getenv("APP_ENV", "dev"),
            app_name=os.getenv("APP_NAME", "multi-tenant-ai-concierge"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=_env_int("APP_PORT", 8000),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/concierge",
            ),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
            vault_addr=os.getenv("VAULT_ADDR", "http://localhost:8200"),
            vault_token=os.getenv("VAULT_TOKEN", "change-me"),
            widget_issuer=os.getenv("WIDGET_ISSUER", "concierge-widget"),
            widget_token_ttl_seconds=_env_int("WIDGET_TOKEN_TTL_SECONDS", 300),
            widget_shared_secret=os.getenv("WIDGET_SHARED_SECRET", "dev-widget-secret"),
            widget_allowed_origins=_env_csv(
                "WIDGET_ALLOWED_ORIGINS",
                ("http://localhost:3000", "http://localhost:5173"),
            ),
            tenant_id_header=os.getenv("TENANT_ID_HEADER", "X-Tenant-Id"),
            request_id_header=os.getenv("REQUEST_ID_HEADER", "X-Request-Id"),
            actor_role_header=os.getenv("ACTOR_ROLE_HEADER", "X-Actor-Role"),
            actor_subject_header=os.getenv("ACTOR_SUBJECT_HEADER", "X-Actor-Subject"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            gemini_api_key=gemini_api_key,
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            chat_model=(
                os.getenv("GEMINI_CHAT_MODEL", default_chat_model)
                if gemini_api_key
                else os.getenv("CHAT_MODEL", "gpt-4.1-mini")
            ),
            classifier_model=os.getenv("CLASSIFIER_MODEL", "classifier.onnx"),
            otel_exporter_otlp_endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://localhost:4317",
            ),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "concierge-api"),
        )

    @property
    def widget_origin_set(self) -> set[str]:
        return set(self.widget_allowed_origins)

    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    def as_dict(self) -> dict[str, object]:
        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "app_host": self.app_host,
            "app_port": self.app_port,
            "database_url": self.database_url,
            "redis_url": self.redis_url,
            "minio_endpoint": self.minio_endpoint,
            "vault_addr": self.vault_addr,
            "widget_issuer": self.widget_issuer,
            "widget_token_ttl_seconds": self.widget_token_ttl_seconds,
            "widget_allowed_origins": self.widget_allowed_origins,
            "tenant_id_header": self.tenant_id_header,
            "request_id_header": self.request_id_header,
            "actor_role_header": self.actor_role_header,
            "actor_subject_header": self.actor_subject_header,
            "embedding_model": self.embedding_model,
            "chat_model": self.chat_model,
            "classifier_model": self.classifier_model,
            "otel_exporter_otlp_endpoint": self.otel_exporter_otlp_endpoint,
            "otel_service_name": self.otel_service_name,
            "has_openai_api_key": bool(self.openai_api_key),
            "has_gemini_api_key": bool(self.gemini_api_key),
            "has_vault_token": bool(self.vault_token),
            "has_widget_shared_secret": bool(self.widget_shared_secret),
        }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return a cached settings object for the current process."""

    return AppSettings.from_env()
