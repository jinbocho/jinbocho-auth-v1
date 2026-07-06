from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.infrastructure.database import session as db_session
from app.limiter import limiter
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _test_engine():
    """The production engine pools connections across requests, which is
    correct for a single long-lived event loop (uvicorn) but breaks when many
    sequential test requests share one event loop with pooled asyncpg
    connections — surfaces as "another operation is in progress" / "attached
    to a different loop". NullPool gives every request its own connection."""
    db_session.engine = create_async_engine(
        settings.database_url, echo=settings.debug, poolclass=NullPool
    )
    db_session.AsyncSessionLocal = async_sessionmaker(db_session.engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    """Invite/forgot-password endpoints send real email via the configured SMTP
    settings (.env has real Gmail credentials for local dev). Force the
    console fallback so integration tests never hit live SMTP."""
    monkeypatch.setattr(settings, "smtp_host", None)


@pytest.fixture(autouse=True)
def no_rate_limiting():
    """Running the whole file legitimately exceeds /auth/register's 5/minute
    limit (most tests register a fresh library via test_library_and_user).
    Disable rate limiting for tests; it has no use-case-level behavior to verify."""
    limiter.enabled = False


@pytest.fixture
async def async_client():
    """Create a FastAPI test client.

    follow_redirects=True: routes like POST /v1/users are registered as "/"
    under the /users prefix, so FastAPI 307-redirects the no-trailing-slash
    path tests use to the trailing-slash one; httpx doesn't follow redirects
    by default.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def test_library_and_user(async_client):
    """Register a test library and user, return library_id and tokens.

    The DB isn't reset between tests, so a hardcoded email would collide
    (409) after the first test that uses this fixture — each call gets its
    own email instead.
    """
    email = f"admin-{uuid4().hex}@test.com"
    register_response = await async_client.post(
        "/v1/auth/register",
        json={
            "library_name": "Test Library",
            "admin_email": email,
            "admin_password": "Password123!",
            "admin_full_name": "Admin User",
            "accepted_privacy_version": "1.0",
            "accepted_terms_version": "1.0",
        },
    )
    assert register_response.status_code == 201
    data = register_response.json()
    return {
        "library_id": data["library_id"],
        "user_id": data["user_id"],
        "email": email,
        "password": "Password123!",
    }
