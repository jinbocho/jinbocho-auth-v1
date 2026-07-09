from datetime import datetime, timedelta, timezone

import pytest

from app.application.use_cases.users import (
	ConfirmEmailChangeInput,
	ConfirmEmailChangeUseCase,
	RequestEmailChangeInput,
	RequestEmailChangeUseCase,
)
from app.domain.entities import EmailChangeToken
from app.domain.exceptions import (
	EmailAlreadyRegisteredError,
	EmailChangeTokenAlreadyUsedError,
	EntityNotFoundError,
	InvalidEmailChangeTokenError,
)


@pytest.fixture
def request_use_case(mock_user_repo, mock_email_change_token_repo, fake_email_sender, token_service):
	return RequestEmailChangeUseCase(
		mock_user_repo, mock_email_change_token_repo, fake_email_sender, token_service,
		expire_minutes=30, frontend_base_url="http://localhost:5173",
	)


@pytest.fixture
def confirm_use_case(mock_user_repo, mock_email_change_token_repo, token_service):
	return ConfirmEmailChangeUseCase(mock_user_repo, mock_email_change_token_repo, token_service)


@pytest.mark.asyncio
async def test_request_email_change_sends_verification_to_new_address(
	request_use_case, mock_user_repo, mock_email_change_token_repo, fake_email_sender, test_user,
):
	await mock_user_repo.save(test_user)

	await request_use_case.execute(
		RequestEmailChangeInput(user_id=test_user.id, new_email="new@example.com")
	)

	assert test_user.email == "test@example.com", "email must not change until confirmed"
	assert len(fake_email_sender.sent) == 1
	assert fake_email_sender.sent[0]["to_email"] == "new@example.com"
	assert "confirm-email-change?token=" in fake_email_sender.sent[0]["link"]
	tokens = list(mock_email_change_token_repo.tokens.values())
	assert len(tokens) == 1
	assert tokens[0].new_email == "new@example.com"
	assert tokens[0].used_at is None


@pytest.mark.asyncio
async def test_request_email_change_is_noop_for_same_email(
	request_use_case, mock_user_repo, mock_email_change_token_repo, fake_email_sender, test_user,
):
	await mock_user_repo.save(test_user)

	await request_use_case.execute(
		RequestEmailChangeInput(user_id=test_user.id, new_email=test_user.email)
	)

	assert fake_email_sender.sent == []
	assert mock_email_change_token_repo.tokens == {}


@pytest.mark.asyncio
async def test_request_email_change_rejects_email_taken_by_another_user(
	request_use_case, mock_user_repo, test_user, test_library,
):
	await mock_user_repo.save(test_user)
	from app.domain.entities import User, UserRole
	from uuid import uuid4

	other = User(
		id=uuid4(), library_id=test_library.id, email="taken@example.com",
		password_hash="x", full_name="Other", role=UserRole.VIEWER,
	)
	await mock_user_repo.save(other)

	with pytest.raises(EmailAlreadyRegisteredError):
		await request_use_case.execute(
			RequestEmailChangeInput(user_id=test_user.id, new_email="taken@example.com")
		)


@pytest.mark.asyncio
async def test_request_email_change_raises_for_unknown_user(request_use_case):
	from uuid import uuid4

	with pytest.raises(EntityNotFoundError):
		await request_use_case.execute(RequestEmailChangeInput(user_id=uuid4(), new_email="x@example.com"))


@pytest.mark.asyncio
async def test_request_email_change_invalidates_earlier_pending_token(
	request_use_case, mock_user_repo, mock_email_change_token_repo, test_user,
):
	await mock_user_repo.save(test_user)

	await request_use_case.execute(
		RequestEmailChangeInput(user_id=test_user.id, new_email="first@example.com")
	)
	first_token = next(iter(mock_email_change_token_repo.tokens.values()))

	await request_use_case.execute(
		RequestEmailChangeInput(user_id=test_user.id, new_email="second@example.com")
	)

	assert first_token.used_at is not None
	tokens = list(mock_email_change_token_repo.tokens.values())
	second_token = next(t for t in tokens if t.id != first_token.id)
	assert second_token.used_at is None
	assert second_token.new_email == "second@example.com"


@pytest.mark.asyncio
async def test_confirm_email_change_updates_user_email(
	confirm_use_case, mock_user_repo, mock_email_change_token_repo, token_service, test_user,
):
	await mock_user_repo.save(test_user)
	raw_token = "raw-token-value"
	now = datetime.now(timezone.utc)
	await mock_email_change_token_repo.save(
		EmailChangeToken(
			user_id=test_user.id,
			new_email="confirmed@example.com",
			token_hash=token_service.hash_token(raw_token),
			expires_at=now + timedelta(minutes=30),
		)
	)

	await confirm_use_case.execute(ConfirmEmailChangeInput(token=raw_token))

	assert test_user.email == "confirmed@example.com"
	saved_token = next(iter(mock_email_change_token_repo.tokens.values()))
	assert saved_token.used_at is not None


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_unknown_token(confirm_use_case):
	with pytest.raises(InvalidEmailChangeTokenError):
		await confirm_use_case.execute(ConfirmEmailChangeInput(token="does-not-exist"))


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_expired_token(
	confirm_use_case, mock_user_repo, mock_email_change_token_repo, token_service, test_user,
):
	await mock_user_repo.save(test_user)
	raw_token = "expired-token"
	now = datetime.now(timezone.utc)
	await mock_email_change_token_repo.save(
		EmailChangeToken(
			user_id=test_user.id,
			new_email="confirmed@example.com",
			token_hash=token_service.hash_token(raw_token),
			expires_at=now - timedelta(minutes=1),
		)
	)

	with pytest.raises(InvalidEmailChangeTokenError):
		await confirm_use_case.execute(ConfirmEmailChangeInput(token=raw_token))
	assert test_user.email == "test@example.com"


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_already_used_token(
	confirm_use_case, mock_user_repo, mock_email_change_token_repo, token_service, test_user,
):
	await mock_user_repo.save(test_user)
	raw_token = "used-token"
	now = datetime.now(timezone.utc)
	await mock_email_change_token_repo.save(
		EmailChangeToken(
			user_id=test_user.id,
			new_email="confirmed@example.com",
			token_hash=token_service.hash_token(raw_token),
			expires_at=now + timedelta(minutes=30),
			used_at=now,
		)
	)

	with pytest.raises(EmailChangeTokenAlreadyUsedError):
		await confirm_use_case.execute(ConfirmEmailChangeInput(token=raw_token))


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_race_condition_on_uniqueness(
	confirm_use_case, mock_user_repo, mock_email_change_token_repo, token_service, test_user, test_library,
):
	await mock_user_repo.save(test_user)
	from app.domain.entities import User, UserRole
	from uuid import uuid4

	# Someone else claimed the address between request and confirmation.
	other = User(
		id=uuid4(), library_id=test_library.id, email="raced@example.com",
		password_hash="x", full_name="Other", role=UserRole.VIEWER,
	)
	await mock_user_repo.save(other)

	raw_token = "raced-token"
	now = datetime.now(timezone.utc)
	await mock_email_change_token_repo.save(
		EmailChangeToken(
			user_id=test_user.id,
			new_email="raced@example.com",
			token_hash=token_service.hash_token(raw_token),
			expires_at=now + timedelta(minutes=30),
		)
	)

	with pytest.raises(EmailAlreadyRegisteredError):
		await confirm_use_case.execute(ConfirmEmailChangeInput(token=raw_token))
	assert test_user.email == "test@example.com"
