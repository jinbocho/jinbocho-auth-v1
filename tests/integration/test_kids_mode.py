from uuid import uuid4

import jwt
import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def kids_module_enabled(monkeypatch):
    """Kids mode is gated on the "kids" module being enabled (Pro-tier gate,
    see UpdateLibraryUseCase) — force it on for this whole file, which is
    about the kids-mode flow itself, not this particular business gate."""
    monkeypatch.setattr(settings, "jinbocho_features", "catalog,auth,kids")


async def _login(async_client, email: str, password: str) -> str:
    response = await async_client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _decode(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience
    )


@pytest.mark.asyncio
async def test_enabling_kids_mode_requires_kids_module(async_client, test_library_and_user, monkeypatch):
    """Kids mode is its own independently-gated optional module — the "ai"
    module being enabled is not sufficient on its own to unlock it."""
    monkeypatch.setattr(settings, "jinbocho_features", "catalog,auth,ai")  # "ai" but no "kids"
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    response = await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"kids_mode_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_enabling_kids_mode_succeeds_without_ai_module(async_client, test_library_and_user, monkeypatch):
    """Kids mode must be enable-able even when the "ai" module is absent —
    it no longer requires AI, only its own "kids" module flag."""
    monkeypatch.setattr(settings, "jinbocho_features", "catalog,auth,kids")  # "kids" but no "ai"
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    response = await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"kids_mode_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["kids_mode_enabled"] is True


@pytest.mark.asyncio
async def test_create_child_account_requires_kids_mode_enabled(async_client, test_library_and_user):
    """Kids mode is off by default — child-account creation must be rejected."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    response = await async_client.post(
        f"/v1/libraries/{library_id}/members/children",
        json={"full_name": "Mia", "password": "ChildPass123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_child_account_created_and_logs_in(async_client, test_library_and_user):
    """Full flow: enable kids mode, create a child account, log in as the
    child through the ordinary /login endpoint, and verify the issued token
    carries role=child and kids_mode_enabled=true."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    toggle_response = await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"kids_mode_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["kids_mode_enabled"] is True

    create_response = await async_client.post(
        f"/v1/libraries/{library_id}/members/children",
        json={"full_name": "Mia", "password": "ChildPass123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_response.status_code == 201
    child_data = create_response.json()
    assert child_data["full_name"] == "Mia"
    assert child_data["email"].endswith("@kids.jinbocho.internal")

    child_token = await _login(async_client, child_data["email"], "ChildPass123!")
    claims = _decode(child_token)
    assert claims["role"] == "child"
    assert claims["kids_mode_enabled"] is True
    assert claims["library_id"] == library_id


@pytest.mark.asyncio
async def test_access_token_carries_language_claim(async_client, test_library_and_user):
    """catalog-service/ai-service read this claim to generate AI content
    (quiz, discussion, incipit, tags) in the reader's own language instead
    of the book's — see TokenService.create_access_token."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])

    update_response = await async_client.patch(
        "/v1/users/me",
        json={"language": "it"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_response.status_code == 200

    fresh_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    claims = _decode(fresh_token)
    assert claims["language"] == "it"


@pytest.mark.asyncio
async def test_create_child_account_non_admin_returns_403(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"kids_mode_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    viewer_email = f"viewer-{uuid4().hex}@test.com"
    await async_client.post(
        "/v1/users",
        json={"email": viewer_email, "full_name": "Viewer", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]
    await async_client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "Viewer123!"})
    viewer_token = await _login(async_client, viewer_email, "Viewer123!")

    response = await async_client.post(
        f"/v1/libraries/{library_id}/members/children",
        json={"full_name": "Mia", "password": "ChildPass123!"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_child_password_reset_routes_to_guardian_email(async_client, test_library_and_user, capsys):
    """A child's `email` is non-deliverable — the password-setup link must go
    to the guardian's real email instead, proving guardian_email is wired
    through issue_password_setup_link."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]
    admin_email = test_library_and_user["email"]

    await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"kids_mode_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    create_response = await async_client.post(
        f"/v1/libraries/{library_id}/members/children",
        json={"full_name": "Mia", "password": "ChildPass123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    child_email = create_response.json()["email"]
    capsys.readouterr()  # discard the invite/registration console emails above

    response = await async_client.post("/v1/auth/forgot-password", json={"email": child_email})
    assert response.status_code == 204

    output = capsys.readouterr().out
    to_line = next(line for line in output.splitlines() if line.strip().startswith("To:"))
    assert admin_email in to_line
    assert child_email not in to_line
