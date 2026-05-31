"""Global exception handlers for the application."""

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def configure_exception_handlers(app):
    """Configure all exception handlers for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
