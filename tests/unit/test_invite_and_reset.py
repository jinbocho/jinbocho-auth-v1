import pytest
from uuid import uuid4

from app.application.use_cases.auth import (
    RequestPasswordResetInput,
    RequestPasswordResetUseCase,
    ResetPasswordInput,
    ResetPasswordUseCase,
)
from app.application.use_cases.users import CreateUserInput, CreateUserUseCase
from app.domain.entities import User, UserRole


@pytest.mark.asyncio
async def test_create_user_does_not_take_a_password(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    """Inviting a user must not let the admin pick their password."""
    use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )

    result = await use_case.execute(
        CreateUserInput(library_id=uuid4(), email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )

    saved = await mock_user_repo.find_by_id(result.id)
    assert saved is not None
    # The placeholder hash must be unusable: nobody knows the random value it hashes.
    assert saved.password_hash


@pytest.mark.asyncio
async def test_create_user_sends_invite_email_with_setup_link(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )

    await use_case.execute(
        CreateUserInput(library_id=uuid4(), email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )

    assert len(fake_email_sender.sent) == 1
    sent = fake_email_sender.sent[0]
    assert sent["to_email"] == "newbie@example.com"
    assert sent["purpose"] == "invite"
    assert "token=" in sent["link"]

    assert len(mock_password_reset_token_repo.tokens) == 1
    token = next(iter(mock_password_reset_token_repo.tokens.values()))
    assert token.purpose == "invite"
    assert token.used_at is None


@pytest.mark.asyncio
async def test_invited_user_can_set_password_via_the_link(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    """End-to-end: invite issues a token, and that same token (generic
    reset-password flow) lets the invitee set their first password."""
    create_use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    await create_use_case.execute(
        CreateUserInput(library_id=uuid4(), email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )

    token = next(iter(mock_password_reset_token_repo.tokens.values()))
    # The use case only ever sees the hash; recover the raw token from the email link.
    sent_link = fake_email_sender.sent[0]["link"]
    raw_token = sent_link.split("token=")[1].split("&")[0]

    reset_use_case = ResetPasswordUseCase(mock_user_repo, mock_password_reset_token_repo, token_service, password_hasher)
    await reset_use_case.execute(ResetPasswordInput(token=raw_token, new_password="MyOwnPassword123"))

    user = await mock_user_repo.find_by_id(token.user_id)
    assert password_hasher.verify("MyOwnPassword123", user.password_hash)
    # password_set_at is the "invite no longer pending" signal shown in the UI.
    assert user.password_set_at is not None

    # The invite token must now be single-use, same as a forgot-password token.
    with pytest.raises(ValueError):
        await reset_use_case.execute(ResetPasswordInput(token=raw_token, new_password="AnotherOne123"))


@pytest.mark.asyncio
async def test_request_password_reset_still_works_for_existing_user(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    """Regression: generalizing the email sender / token issuing must not
    break the original forgot-password flow."""
    user = User(
        library_id=uuid4(),
        email="existing@example.com",
        password_hash=password_hasher.hash("OldPassword123"),
        full_name="Existing User",
        role=UserRole.ADMIN,
    )
    await mock_user_repo.save(user)

    use_case = RequestPasswordResetUseCase(
        mock_user_repo, mock_password_reset_token_repo, fake_email_sender, token_service,
        password_reset_expire_minutes=15, frontend_base_url="http://localhost:5173",
    )
    await use_case.execute(RequestPasswordResetInput(email=user.email))

    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["purpose"] == "reset"
    token = next(iter(mock_password_reset_token_repo.tokens.values()))
    assert token.purpose == "reset"
