import base64
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def _validate_database_urls(migration_database_url: str, app_database_url: str) -> None:
    migration = make_url(migration_database_url)
    app = make_url(app_database_url)
    if migration.username == app.username:
        raise ValueError(
            "MIGRATION_DATABASE_URL and APP_DATABASE_URL must use different users; "
            f"both are {migration.username!r}"
        )


class Settings(BaseSettings):
    # Database settings (superuser for migrations, restricted app role at runtime)
    app_database_url: str
    migration_database_url: str

    # Operational settings
    service_name: str = "care-episode"
    env: str = "production"
    log_level: str = "info"
    port: int = 8015
    trusted_proxy_hops: int = Field(default=1, ge=0)

    # Input validation settings
    max_content_length: int = Field(default=16_384, gt=0)

    # Authorization settings
    authorization_policies_dir: Path = Field(default=Path("policies"))
    authorization_policy_cache_ttl: int = Field(default=60, ge=0)
    
    # JWT authentication settings
    jwt_public_key: str | None = Field(default=None)
    jwt_jwks_uri: str | None = Field(default=None)
    jwt_audience: str | list[str] = Field(default="care-episode")
    # Rate limit settings
    rate_limit_storage_uri: str = "memory://"
    health_rate_limit: str = "600 per minute"
    care_episode_read_rate_limit: str = "120 per minute"
    care_episode_write_rate_limit: str = "60 per minute"

    # UI-facing upstream timeouts — each must stay at or below 10 seconds.
    chat_service_timeout_seconds: float = Field(default=10.0, gt=0, le=10.0)

    # Clinical risk inference (Bedrock/OpenAI-compatible completions API)
    inference_completions_url: str = ""
    inference_api_key: str | None = None
    inference_model: str = ""
    inference_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    inference_timeout_seconds: float = Field(default=10.0, gt=0, le=10.0)
    risk_escalation_enabled: bool = True
    clinical_risk_alert_from_email: str = "care-episode-alerts@neosofia.tech"
    notification_service_timeout_seconds: float = Field(default=10.0, gt=0, le=10.0)

    # Demo template patient (DEMO-123); exposed on principal as demoTemplatePatientUuid for Cedar.
    demo_template_patient_uuid: str = Field(
        default="00000000-0000-7000-8000-000000002847",
        min_length=36,
    )

    # Service-to-service auth and registry discovery
    authentication_service_base_url: str = ""
    care_episode_client_secret: str = ""
    authentication_token_timeout_seconds: float = Field(default=10.0, gt=0, le=10.0)
    service_registry_cache_ttl_seconds: int = Field(default=60, ge=0)

    # Gunicorn — worker request silence limit; slightly above per-hop UI timeouts to avoid end-of-request races
    web_concurrency: int = Field(default=1, ge=1)
    gunicorn_threads: int = Field(default=32, ge=1)
    gunicorn_timeout: int = Field(default=15, ge=1)
    
    # CORS settings
    frontend_url: str = Field(default="http://localhost:5173")
    gunicorn_keepalive: int = Field(default=5, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @field_validator("jwt_audience", mode="before")
    def normalize_jwt_audience(cls, value: str | list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]

    @field_validator(
        "port",
        "trusted_proxy_hops",
        "max_content_length",
        "authorization_policy_cache_ttl",
        "web_concurrency",
        "gunicorn_threads",
        "gunicorn_timeout",
        "gunicorn_keepalive",
        mode="before",
    )
    @classmethod
    def _normalize_optional_int_env(cls, value: object, info) -> object:
        env_var = info.field_name.upper()
        # Some platforms inject empty strings for optional numeric env vars.
        # Returning None lets pydantic apply the field default.
        if isinstance(value, str) and not value.strip():
            return None
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"{env_var} must be an integer, got {value!r}") from exc
        return value

    @field_validator("app_database_url", "migration_database_url", mode="before")
    @classmethod
    def _require_non_empty_database_url(cls, value: object, info) -> str:
        env_var = info.field_name.upper()
        if value is None or not str(value).strip():
            raise ValueError(f"{env_var} must be set")
        return str(value).strip()

    def model_post_init(self, __context: object) -> None:
        _validate_database_urls(self.migration_database_url, self.app_database_url)

        if not self.jwt_public_key and not self.jwt_jwks_uri:
            raise ValueError("JWT_PUBLIC_KEY or JWT_JWKS_URI must be configured for token validation")

        if not self.authentication_service_base_url.strip():
            jwks = (self.jwt_jwks_uri or "").strip()
            suffix = "/.well-known/jwks.json"
            if jwks.endswith(suffix):
                object.__setattr__(
                    self,
                    "authentication_service_base_url",
                    jwks[: -len(suffix)].rstrip("/"),
                )

        # Decode Base64 PEM keys passed in via environment variables
        if self.jwt_public_key and self.jwt_public_key != "DEFAULT_PUBLIC_KEY":
            try:
                decoded = base64.b64decode(self.jwt_public_key).decode("utf-8")
                object.__setattr__(self, "jwt_public_key", decoded)
            except Exception as e:
                # If it's already a PEM string (not base64), or we provided a JWKS URI, just continue
                if "BEGIN PUBLIC KEY" not in self.jwt_public_key:
                    raise ValueError(f"Failed to decode base64 jwt_public_key: {e}")


settings = Settings()  # type: ignore[call-arg]