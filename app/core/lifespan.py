"""Application lifespan management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application lifespan events.

    Currently a no-op, but can be extended for:
    - Database connection pooling
    - Cache initialization
    - Background task scheduling
    """
    yield
