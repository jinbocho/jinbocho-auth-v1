from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import settings
from app.infrastructure import models as infrastructure_models
from app.infrastructure.database.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    infrastructure_models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Jinbocho Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}
