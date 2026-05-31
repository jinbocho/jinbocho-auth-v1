"""Jinbocho Auth Service FastAPI application factory."""

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core import OPENAPI_CONFIG, configure_exception_handlers, lifespan
from app.limiter import limiter
import app.infrastructure.models  # noqa: F401 — registers ORM models with SQLAlchemy


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

    # Include routers
    app.include_router(v1_router, prefix="/v1")

    # Health check endpoint
    @app.get(
        "/health",
        tags=["health"],
        summary="Health check",
        description="Check if the service is running.",
    )
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "auth-service"}

    return app


app = create_app()
