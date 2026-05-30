from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import router as v1_router
from app.limiter import limiter
import app.infrastructure.models  # noqa: F401 — registers ORM models with SQLAlchemy


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Jinbocho Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(v1_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}
