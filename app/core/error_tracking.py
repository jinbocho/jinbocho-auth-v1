import sentry_sdk

from app.config import settings


def configure_error_tracking(*, service_name: str) -> None:
    """Wire Sentry/GlitchTip error reporting (ADR-012 Phase 1). No-op unless
    SENTRY_DSN is set — a deployment without an error-tracking backend behaves
    exactly as before. Works unmodified against GlitchTip (self-hosted,
    Sentry-protocol-compatible) or Sentry Cloud EU — only the DSN differs.

    Domain exceptions (LookupError/PermissionError/ValueError/...) are all
    caught by configure_exception_handlers before they can propagate, so only
    genuinely unhandled bugs ever reach here — no extra 4xx filtering needed
    on top of the SDK's default (it only reports 5xx by default).
    """
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        server_name=service_name,
        send_default_pii=False,
        traces_sample_rate=0.0,  # tracing already covered by OpenTelemetry (ADR-012)
    )
