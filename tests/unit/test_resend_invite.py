import pytest
from uuid import uuid4

from app.application.use_cases.users import (
    CreateUserInput,
    CreateUserUseCase,
    ResendInviteInput,
    ResendInviteUseCase,
)
from app.domain.entities import UserRole
from app.domain.exceptions import EntityNotFoundError, InvalidResetTokenError


@pytest.mark.asyncio
async def test_resend_invite_sends_new_link_and_invalidates_old_one(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    library_id = uuid4()
    create_use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    created = await create_use_case.execute(
        CreateUserInput(library_id=library_id, email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )
    original_token = next(iter(mock_password_reset_token_repo.tokens.values()))

    resend_use_case = ResendInviteUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    await resend_use_case.execute(ResendInviteInput(user_id=created.id, requester_library_id=library_id))

    assert len(fake_email_sender.sent) == 2
    assert fake_email_sender.sent[1]["purpose"] == "invite"

    assert mock_password_reset_token_repo.tokens[original_token.id].used_at is not None
    new_tokens = [
        t for t in mock_password_reset_token_repo.tokens.values() if t.id != original_token.id
    ]
    assert len(new_tokens) == 1
    assert new_tokens[0].used_at is None


@pytest.mark.asyncio
async def test_resend_invite_rejects_user_who_already_set_password(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    library_id = uuid4()
    create_use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    created = await create_use_case.execute(
        CreateUserInput(library_id=library_id, email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )
    user = await mock_user_repo.find_by_id(created.id)
    user.password_set_at = user.created_at
    await mock_user_repo.save(user)

    resend_use_case = ResendInviteUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    with pytest.raises(InvalidResetTokenError):
        await resend_use_case.execute(ResendInviteInput(user_id=created.id, requester_library_id=library_id))


@pytest.mark.asyncio
async def test_resend_invite_requires_user_in_same_library(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    create_use_case = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    created = await create_use_case.execute(
        CreateUserInput(library_id=uuid4(), email="newbie@example.com", full_name="New Bie", role=UserRole.VIEWER)
    )

    resend_use_case = ResendInviteUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    with pytest.raises(EntityNotFoundError):
        await resend_use_case.execute(ResendInviteInput(user_id=created.id, requester_library_id=uuid4()))
