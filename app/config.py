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
    frontend_base_url: str = "http://localhost:5173"

    # SMTP — leave smtp_host empty to use console fallback (development)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_timeout_seconds: int = 10
    email_from: str = "noreply@jinbocho.local"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()  # type: ignore[call-arg]  # required fields come from .env / environment
