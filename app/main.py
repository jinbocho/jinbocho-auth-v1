"""Jinbocho Auth Service FastAPI application factory."""

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import settings
from app.core import (
    OPENAPI_CONFIG,
    configure_error_tracking,
    configure_exception_handlers,
    configure_logging,
    configure_telemetry,
    instrument_logging,
    lifespan,
)
from app.infrastructure.database.session import engine
from app.limiter import limiter
import app.infrastructure.models as _models  # noqa: F401 — registers ORM models with SQLAlchemy

instrument_logging()
configure_logging(debug=settings.debug, otel_enabled=settings.otel_enabled)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(**OPENAPI_CONFIG, lifespan=lifespan)

    # Configure rate limiting
    app.state.limiter = limiter

    # Configure exception handlers
    configure_exception_handlers(app)

    # Error tracking (ADR-012) — no-op unless SENTRY_DSN is set
    configure_error_tracking(service_name="auth-service")

    # Observability (ADR-012) — no-op unless OTEL_ENABLED=true
    configure_telemetry(app, service_name="auth-service", engine=engine)

    # Include routers
    app.include_router(v1_router, prefix="/v1")

    # Health check endpoint
    @app.get(
        "/health",
        tags=["health"],
        summary="Health check",
        description="Check if the service is running.",
    )
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "auth-service"}

    return app


app = create_app()
