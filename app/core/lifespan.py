import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi import FastAPI

from app.config import settings
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.repositories.password_reset_token_repository import (
    SQLAlchemyPasswordResetTokenRepository,
)
from app.infrastructure.repositories.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)

logger = logging.getLogger(__name__)


async def _cleanup_expired_tokens() -> None:
    """Delete expired/used password-reset tokens and expired refresh tokens."""
    async with AsyncSessionLocal() as session:
        try:
            reset_repo = SQLAlchemyPasswordResetTokenRepository(session)
            refresh_repo = SQLAlchemyRefreshTokenRepository(session)
            n_reset = await reset_repo.cleanup_expired()
            n_refresh = await refresh_repo.cleanup_expired()
            await session.commit()
            logger.info(
                "Token cleanup: removed %d password-reset token(s) and %d refresh token(s)",
                n_reset,
                n_refresh,
            )
        except Exception:
            await session.rollback()
            logger.exception("Token cleanup job failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _cleanup_expired_tokens,
        trigger="interval",
        hours=settings.token_cleanup_interval_hours,
        id="cleanup_expired_tokens",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Token cleanup scheduler started (interval: %dh)", settings.token_cleanup_interval_hours
    )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Token cleanup scheduler stopped")
