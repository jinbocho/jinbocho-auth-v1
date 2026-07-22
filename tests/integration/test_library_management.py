from uuid import uuid4

import pytest


async def _login(async_client, email: str, password: str) -> str:
    response = await async_client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# Update library
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_library_name_and_description(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    response = await async_client.patch(
        f"/v1/libraries/{library_id}",
        json={"name": "Renamed Library", "description": "Our cozy library"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Renamed Library"
    assert data["description"] == "Our cozy library"


@pytest.mark.asyncio
async def test_update_library_non_admin_returns_403(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
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
    response = await async_client.patch(
        f"/v1/libraries/{test_library_and_user['library_id']}",
        json={"name": "Hijacked"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_library_wrong_library_returns_403(async_client, test_library_and_user):
    """Admin cannot update a different library's record."""
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    other_library_id = str(uuid4())

    response = await async_client.patch(
        f"/v1/libraries/{other_library_id}",
        json={"name": "Other"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Confirm deletion (preflight check)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_library_deletion_succeeds_with_correct_credentials(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]
    library_name = (
        await async_client.get(f"/v1/libraries/{library_id}", headers={"Authorization": f"Bearer {token}"})
    ).json()["name"]

    response = await async_client.post(
        f"/v1/libraries/{library_id}/confirm-deletion",
        json={"password": test_library_and_user["password"], "confirm_library_name": library_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_confirm_library_deletion_wrong_password_returns_401(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]
    library_name = (
        await async_client.get(f"/v1/libraries/{library_id}", headers={"Authorization": f"Bearer {token}"})
    ).json()["name"]

    response = await async_client.post(
        f"/v1/libraries/{library_id}/confirm-deletion",
        json={"password": "WrongPassword!", "confirm_library_name": library_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_confirm_library_deletion_wrong_name_returns_400(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]

    response = await async_client.post(
        f"/v1/libraries/{library_id}/confirm-deletion",
        json={"password": test_library_and_user["password"], "confirm_library_name": "Wrong Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Delete library (irreversible)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_library_succeeds_with_correct_credentials(async_client):
    """Full account deletion: register, then delete with correct password + name."""
    email = f"todelete-{uuid4().hex}@test.com"
    reg = await async_client.post(
        "/v1/auth/register",
        json={
            "library_name": "Doomed Library",
            "admin_email": email,
            "admin_password": "Password123!",
            "admin_full_name": "Doomed Admin",
            "accepted_privacy_version": "1.0",
            "accepted_terms_version": "1.0",
        },
    )
    assert reg.status_code == 201
    library_id = reg.json()["library_id"]

    token = await _login(async_client, email, "Password123!")

    response = await async_client.request(
        "DELETE",
        f"/v1/libraries/{library_id}",
        json={"password": "Password123!", "confirm_library_name": "Doomed Library"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # After deletion the token is invalid — the user no longer exists.
    me_response = await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_delete_library_wrong_password_returns_401(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    library_id = test_library_and_user["library_id"]
    library_name = (
        await async_client.get(f"/v1/libraries/{library_id}", headers={"Authorization": f"Bearer {token}"})
    ).json()["name"]

    response = await async_client.request(
        "DELETE",
        f"/v1/libraries/{library_id}",
        json={"password": "WrongPassword!", "confirm_library_name": library_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_library_non_admin_returns_403(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    viewer_email = f"viewer-del-{uuid4().hex}@test.com"
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
    response = await async_client.request(
        "DELETE",
        f"/v1/libraries/{test_library_and_user['library_id']}",
        json={"password": "Viewer123!", "confirm_library_name": "Test Library"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
