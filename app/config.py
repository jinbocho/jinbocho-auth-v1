from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    debug: bool = False
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "jinbocho-auth"
    jwt_audience: str = "jinbocho"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Password reset / invite (first-time password setup)
    password_reset_expire_minutes: int = 15
    invite_expire_minutes: int = 60 * 24 * 7  # 7 days
    email_change_expire_minutes: int = 30
    frontend_base_url: str = "http://localhost:5173"

    # SMTP — leave smtp_host empty to use console fallback (development)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_timeout_seconds: int = 10
    email_from: str = "noreply@jinbocho.local"

    # Scheduled maintenance
    token_cleanup_interval_hours: int = 1

    # Shared secret for service-to-service calls (e.g. catalog-service asking
    # us to send a loan-reminder email) — these don't carry a user JWT.
    internal_service_token: str = ""

    # Observability (ADR-012) — off by default so a service run without the
    # optional Alloy collector container behaves exactly as before.
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://alloy:4318"

    # Error tracking (ADR-012 Phase 1) — off by default. Point at a GlitchTip
    # instance or Sentry Cloud (EU region); only unhandled 5xx bugs are ever
    # reported (see configure_error_tracking).
    sentry_dsn: str | None = None
    sentry_environment: str = "production"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()  # type: ignore[call-arg]  # required fields come from .env / environment
