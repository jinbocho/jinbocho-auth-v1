from uuid import uuid4

import pytest


async def _login(async_client, email, password):
    response = await async_client.post("/v1/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_email_change_full_flow(async_client, test_library_and_user, capsys):
    """Full flow: request change → email goes to the NEW address, not the
    current one → confirm token → old email stops working, new one logs in."""
    access_token = await _login(
        async_client, test_library_and_user["email"], test_library_and_user["password"]
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    new_email = f"new-{uuid4().hex}@test.com"

    change_response = await async_client.post(
        "/v1/users/me/email/change",
        json={"new_email": new_email},
        headers=headers,
    )
    assert change_response.status_code == 204

    output = capsys.readouterr().out
    console_lines = [line for line in output.splitlines() if line.startswith("To:") or line.startswith("Link:")]
    assert any(new_email in line for line in console_lines), "verification link must be sent to the NEW address"
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]

    # Email of record hasn't changed yet — still logs in with the old address.
    still_old_login = await async_client.post(
        "/v1/auth/login",
        json={"email": test_library_and_user["email"], "password": test_library_and_user["password"]},
    )
    assert still_old_login.status_code == 200

    confirm_response = await async_client.post(
        "/v1/auth/confirm-email-change",
        json={"token": raw_token},
    )
    assert confirm_response.status_code == 204

    old_login_after_confirm = await async_client.post(
        "/v1/auth/login",
        json={"email": test_library_and_user["email"], "password": test_library_and_user["password"]},
    )
    assert old_login_after_confirm.status_code == 401

    new_login = await async_client.post(
        "/v1/auth/login",
        json={"email": new_email, "password": test_library_and_user["password"]},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_email_change_rejects_email_already_registered(async_client, test_library_and_user):
    other_email = f"other-{uuid4().hex}@test.com"
    other_register_response = await async_client.post(
        "/v1/auth/register",
        json={
            "library_name": "Other Test Library",
            "admin_email": other_email,
            "admin_password": "Password123!",
            "admin_full_name": "Other Admin",
            "accepted_privacy_version": "1.0",
            "accepted_terms_version": "1.0",
        },
    )
    assert other_register_response.status_code == 201

    access_token = await _login(
        async_client, test_library_and_user["email"], test_library_and_user["password"]
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    change_response = await async_client.post(
        "/v1/users/me/email/change",
        json={"new_email": other_email},
        headers=headers,
    )
    assert change_response.status_code == 409


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_unknown_token(async_client):
    response = await async_client.post(
        "/v1/auth/confirm-email-change",
        json={"token": "not-a-real-token"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_confirm_email_change_token_is_single_use(async_client, test_library_and_user, capsys):
    access_token = await _login(
        async_client, test_library_and_user["email"], test_library_and_user["password"]
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    new_email = f"new-{uuid4().hex}@test.com"

    await async_client.post(
        "/v1/users/me/email/change",
        json={"new_email": new_email},
        headers=headers,
    )
    output = capsys.readouterr().out
    link_line = next(line for line in output.splitlines() if line.startswith("Link:"))
    raw_token = link_line.split("token=")[1].split("&")[0]

    first_confirm = await async_client.post("/v1/auth/confirm-email-change", json={"token": raw_token})
    assert first_confirm.status_code == 204

    second_confirm = await async_client.post("/v1/auth/confirm-email-change", json={"token": raw_token})
    assert second_confirm.status_code == 400
