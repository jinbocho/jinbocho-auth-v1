import pytest


@pytest.mark.asyncio
async def test_register_family_success(async_client):
    """Test successful family registration creates family and admin user."""
    response = await async_client.post(
        "/v1/auth/register",
        json={
            "family_name": "My Test Family",
            "admin_email": "admin@family.com",
            "admin_password": "SecurePassword123!",
            "admin_full_name": "Admin Name",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "family_id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_register_family_sends_welcome_email(async_client, capsys):
    """The admin who creates a family must receive a welcome email with a
    link to log in (console fallback in tests, since SMTP isn't configured)."""
    response = await async_client.post(
        "/v1/auth/register",
        json={
            "family_name": "Welcome Family",
            "admin_email": "welcome-admin@family.com",
            "admin_password": "SecurePassword123!",
            "admin_full_name": "Admin Name",
        },
    )
    assert response.status_code == 201

    console_output = capsys.readouterr().out
    assert "[EMAIL CONSOLE]" in console_output
    assert "welcome-admin@family.com" in console_output
    link_line = next(line for line in console_output.splitlines() if line.startswith("Link:"))
    assert link_line.strip().endswith("/login")


@pytest.mark.asyncio
async def test_login_success(async_client, test_family_and_user):
    """Test successful login returns access and refresh tokens."""
    response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client):
    """Test login with invalid credentials returns 401."""
    response = await async_client.post(
        "/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(async_client, test_family_and_user):
    """Test token refresh rotates tokens."""
    # Login first
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh
    response = await async_client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_token_invalid(async_client):
    """Test refresh with invalid token returns 401."""
    response = await async_client.post(
        "/v1/auth/refresh", json={"refresh_token": "invalid_token_xyz"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(async_client, test_family_and_user):
    """Test logout revokes refresh token."""
    # Login first
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Logout
    response = await async_client.post("/v1/auth/logout", json={"refresh_token": refresh_token})
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_me_success(async_client, test_family_and_user):
    """Test GET /me returns current user info."""
    # Login to get access token
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    # Get current user
    response = await async_client.get(
        "/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_family_and_user["email"]


@pytest.mark.asyncio
async def test_create_user_success(async_client, test_family_and_user):
    """Test inviting a new user in family — no password is chosen by the admin."""
    # Login as admin
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    # Invite new user
    response = await async_client.post(
        "/v1/users",
        json={
            "email": "newuser@test.com",
            "full_name": "New User",
            "role": "editor",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"


@pytest.mark.asyncio
async def test_invited_user_sets_password_and_logs_in(async_client, test_family_and_user, capsys):
    """End to end: invite a user, recover the setup link from the console-email
    fallback, set a password through the generic reset-password endpoint, then
    log in with it."""
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    invite_response = await async_client.post(
        "/v1/users",
        json={"email": "invitee@test.com", "full_name": "Invitee", "role": "viewer"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert invite_response.status_code == 201

    console_output = capsys.readouterr().out
    assert "[EMAIL CONSOLE]" in console_output
    link_line = next(line for line in console_output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]

    reset_response = await async_client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "MyOwnPassword123!"},
    )
    assert reset_response.status_code == 204

    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": "invitee@test.com", "password": "MyOwnPassword123!"},
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_delete_user_success(async_client, test_family_and_user):
    """Regression: deleting a user used to fail with a NotNullViolationError
    on refresh_tokens.user_id (the ORM tried to null the FK instead of
    trusting the DB's ON DELETE CASCADE). Reproduce it faithfully by giving
    the user an actual refresh token row before deleting them."""
    import uuid
    from datetime import datetime, timezone
    from app.infrastructure.database.session import AsyncSessionLocal
    from app.infrastructure.models import RefreshTokenModel

    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    create_response = await async_client.post(
        "/v1/users",
        json={"email": "todelete@test.com", "full_name": "To Delete", "role": "viewer"},
        headers=headers,
    )
    user_id = create_response.json()["id"]

    async with AsyncSessionLocal() as session:
        session.add(
            RefreshTokenModel(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                token_hash="regression-test-token-hash",
                expires_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    delete_response = await async_client.delete(f"/v1/users/{user_id}", headers=headers)
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_update_me_persists_theme_preferences(async_client, test_family_and_user):
    """Regression: SQLAlchemyUserRepository._to_entity used to drop
    theme_name/theme_mode on every read, so a PATCH would write them to the
    DB but the response (and any later GET) would still show null."""
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    patch_response = await async_client.patch(
        "/v1/users/me",
        json={"theme_name": "akabeni", "theme_mode": "dark"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["theme_name"] == "akabeni"
    assert patch_response.json()["theme_mode"] == "dark"

    get_response = await async_client.get("/v1/users/me", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["theme_name"] == "akabeni"
    assert get_response.json()["theme_mode"] == "dark"


@pytest.mark.asyncio
async def test_get_family_success(async_client, test_family_and_user):
    """Test GET /families/{id} returns family info."""
    # Login to get access token
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    # Get family
    response = await async_client.get(
        f"/v1/families/{test_family_and_user['family_id']}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
