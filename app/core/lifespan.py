"""Application lifespan management."""

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.

    Currently a no-op, but can be extended for:
    - Database connection pooling
    - Cache initialization
    - Background task scheduling
    """
    yield
