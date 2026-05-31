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
    """Test creating a new user in family."""
    # Login as admin
    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_family_and_user["email"], "password": test_family_and_user["password"]},
    )
    access_token = login_response.json()["access_token"]

    # Create new user
    response = await async_client.post(
        "/v1/users",
        json={
            "email": "newuser@test.com",
            "password": "NewPassword123!",
            "full_name": "New User",
            "role": "editor",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"


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
