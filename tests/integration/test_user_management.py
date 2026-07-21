from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _login(async_client, email: str, password: str) -> str:
    response = await async_client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _invite_user(async_client, token: str, email: str, role: str = "viewer") -> dict:
    response = await async_client.post(
        "/v1/users",
        json={"email": email, "full_name": "Test User", "role": role},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_returns_library_members(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])

    response = await async_client.get("/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    emails = [u["email"] for u in users]
    assert test_library_and_user["email"] in emails


@pytest.mark.asyncio
async def test_list_users_requires_authentication(async_client):
    response = await async_client.get("/v1/users")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Update user (admin updates another member)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_update_user_role(async_client, test_library_and_user):
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    invited = await _invite_user(async_client, token, f"role-test-{uuid4().hex}@test.com", role="viewer")

    response = await async_client.patch(
        f"/v1/users/{invited['id']}",
        json={"role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


@pytest.mark.asyncio
async def test_admin_can_set_and_clear_birth_year(async_client, test_library_and_user):
    """KID-01: a parent must be able to add/correct a child's birth_year on
    an existing account, not just at creation time."""
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    invited = await _invite_user(async_client, token, f"birthyear-test-{uuid4().hex}@test.com", role="viewer")

    set_response = await async_client.patch(
        f"/v1/users/{invited['id']}",
        json={"birth_year": 2015},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["birth_year"] == 2015

    clear_response = await async_client.patch(
        f"/v1/users/{invited['id']}",
        json={"birth_year": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["birth_year"] is None


@pytest.mark.asyncio
async def test_self_profile_returns_birth_year(async_client, test_library_and_user):
    """GetUserUseCase (GET /v1/users/me) must surface birth_year too, not
    just the admin-facing update/list paths — MyReadingPage derives its own
    age band from this exact endpoint, and a missing field here silently
    made every child's own view fall back to the "unknown band" full
    experience regardless of what birth_year was actually set to."""
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    admin_id = test_library_and_user["user_id"]

    set_response = await async_client.patch(
        f"/v1/users/{admin_id}",
        json={"birth_year": 2015},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert set_response.status_code == 200

    me_response = await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["birth_year"] == 2015


@pytest.mark.asyncio
async def test_non_admin_cannot_update_other_user(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    viewer = await _invite_user(async_client, admin_token, f"viewer-{uuid4().hex}@test.com", role="viewer")

    # Set viewer's password so they can log in
    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]
    await async_client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "Viewer123!"})

    viewer_token = await _login(async_client, viewer["email"], "Viewer123!")
    admin_user = (await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})).json()

    response = await async_client.patch(
        f"/v1/users/{admin_user['id']}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_demote_sole_admin(async_client, test_library_and_user):
    """Last admin protection: demoting the only admin must return 409."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    admin_user = (await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})).json()

    response = await async_client.patch(
        f"/v1/users/{admin_user['id']}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cannot_delete_sole_admin(async_client, test_library_and_user):
    """Last admin protection: deleting the only admin must return 409."""
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    admin_user = (await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})).json()

    response = await async_client.delete(
        f"/v1/users/{admin_user['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_invite_duplicate_email_returns_409(async_client, test_library_and_user):
    """Inviting a user with an already-registered email returns 409."""
    token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    email = f"dup-invite-{uuid4().hex}@test.com"
    await _invite_user(async_client, token, email, role="viewer")

    response = await async_client.post(
        "/v1/users",
        json={"email": email, "full_name": "Duplicate", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Resend invite
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resend_invite_sends_new_link(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    invited = await _invite_user(async_client, admin_token, f"resend-{uuid4().hex}@test.com")
    capsys.readouterr()  # discard first invite email

    response = await async_client.post(
        f"/v1/users/{invited['id']}/resend-invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    output = capsys.readouterr().out
    assert "[EMAIL CONSOLE]" in output
    assert "token=" in output


@pytest.mark.asyncio
async def test_resend_invite_rejects_user_who_set_password(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    invited = await _invite_user(async_client, admin_token, f"setpwd-{uuid4().hex}@test.com")

    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]
    await async_client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "SetPwd123!"})

    response = await async_client.post(
        f"/v1/users/{invited['id']}/resend-invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Export & import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_library_data_returns_roster(async_client, test_library_and_user):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])

    response = await async_client.get("/v1/users/export", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "library" in data
    assert "users" in data
    assert isinstance(data["users"], list)
    emails = [u["email"] for u in data["users"]]
    assert test_library_and_user["email"] in emails
    for user in data["users"]:
        assert "password_hash" not in user


@pytest.mark.asyncio
async def test_export_non_admin_returns_403(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])
    invited = await _invite_user(async_client, admin_token, f"exp-viewer-{uuid4().hex}@test.com")

    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]
    await async_client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "Viewer123!"})

    viewer_token = await _login(async_client, invited["email"], "Viewer123!")
    response = await async_client.get("/v1/users/export", headers={"Authorization": f"Bearer {viewer_token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_users_matches_existing_and_creates_new(async_client, test_library_and_user, capsys):
    admin_token = await _login(async_client, test_library_and_user["email"], test_library_and_user["password"])

    export_response = await async_client.get("/v1/users/export", headers={"Authorization": f"Bearer {admin_token}"})
    exported = export_response.json()
    existing_user = exported["users"][0]
    capsys.readouterr()  # discard any output so far

    new_email = f"import-new-{uuid4().hex}@test.com"
    fake_old_id = str(uuid4())
    import_payload = {
        "users": [
            {
                "id": existing_user["id"],
                "email": existing_user["email"],
                "full_name": existing_user["full_name"],
                "role": existing_user["role"],
            },
            {
                "id": fake_old_id,
                "email": new_email,
                "full_name": "Imported User",
                "role": "viewer",
            },
        ]
    }

    response = await async_client.post(
        "/v1/users/import",
        json=import_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] == 1
    assert data["created"] == 1

    # Matched user keeps the same real ID
    assert data["user_id_map"][existing_user["id"]] == existing_user["id"]

    # New user gets a fresh ID (different from the fake old ID)
    assert data["user_id_map"][fake_old_id] != fake_old_id

    # The new user was invited by email
    output = capsys.readouterr().out
    assert new_email in output
