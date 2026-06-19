import pytest
import asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    """Invite/forgot-password endpoints send real email via the configured SMTP
    settings (.env has real Gmail credentials for local dev). Force the
    console fallback so integration tests never hit live SMTP."""
    monkeypatch.setattr(settings, "smtp_host", None)


@pytest.fixture
async def async_client():
    """Create a FastAPI test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_family_and_user(async_client):
    """Register a test family and user, return family_id and tokens."""
    register_response = await async_client.post(
        "/v1/auth/register",
        json={
            "family_name": "Test Family",
            "admin_email": "admin@test.com",
            "admin_password": "Password123!",
            "admin_full_name": "Admin User",
        },
    )
    assert register_response.status_code == 201
    data = register_response.json()
    return {
        "family_id": data["family_id"],
        "user_id": data["user_id"],
        "email": "admin@test.com",
        "password": "Password123!",
    }
