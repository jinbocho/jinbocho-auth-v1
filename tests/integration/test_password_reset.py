import pytest


@pytest.mark.asyncio
async def test_forgot_password_returns_204_for_known_email(async_client, test_library_and_user):
    """Always returns 204 — no information leakage about whether the email exists."""
    response = await async_client.post(
        "/v1/auth/forgot-password",
        json={"email": test_library_and_user["email"]},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_forgot_password_returns_204_for_unknown_email(async_client):
    """Anti-enumeration: 204 even when the email is not registered."""
    response = await async_client.post(
        "/v1/auth/forgot-password",
        json={"email": "nobody@notregistered.example"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_forgot_password_sends_reset_link(async_client, test_library_and_user, capsys):
    """A reset email is sent with a link containing a token."""
    await async_client.post(
        "/v1/auth/forgot-password",
        json={"email": test_library_and_user["email"]},
    )

    output = capsys.readouterr().out
    assert "[EMAIL CONSOLE]" in output
    assert test_library_and_user["email"] in output
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    assert "token=" in link_line


@pytest.mark.asyncio
async def test_reset_password_success(async_client, test_library_and_user, capsys):
    """Full flow: request reset → consume token → log in with new password."""
    await async_client.post(
        "/v1/auth/forgot-password",
        json={"email": test_library_and_user["email"]},
    )
    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]

    reset_response = await async_client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword456!"},
    )
    assert reset_response.status_code == 204

    login_response = await async_client.post(
        "/v1/auth/login",
        json={"email": test_library_and_user["email"], "password": "NewPassword456!"},
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_token_is_single_use(async_client, test_library_and_user, capsys):
    """A reset token can only be consumed once; a second attempt returns 400."""
    await async_client.post(
        "/v1/auth/forgot-password",
        json={"email": test_library_and_user["email"]},
    )
    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]

    await async_client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword456!"},
    )

    second = await async_client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPassword789!"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(async_client):
    """A completely made-up token returns 400, not 500."""
    response = await async_client.post(
        "/v1/auth/reset-password",
        json={"token": "this-is-not-a-valid-token", "new_password": "Password123!"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(async_client):
    """Registering the same admin email twice returns 409 Conflict."""
    payload = {
        "library_name": "Duplicate Library",
        "admin_email": "duplicate@test.com",
        "admin_password": "Password123!",
        "admin_full_name": "Dup Admin",
        "accepted_privacy_version": "1.0",
        "accepted_terms_version": "1.0",
    }
    first = await async_client.post("/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await async_client.post("/v1/auth/register", json=payload)
    assert second.status_code == 409
