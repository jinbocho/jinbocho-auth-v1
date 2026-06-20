import pytest
from uuid import uuid4

from app.application.use_cases.auth import pwd_context
from app.application.use_cases.users import (
	CreateUserUseCase,
	ExportFamilyDataInput,
	ExportFamilyDataUseCase,
	ImportUserItem,
	ImportUsersInput,
	ImportUsersUseCase,
	UpdateUserUseCase,
)
from app.domain.entities import Family, User


@pytest.mark.asyncio
async def test_export_family_data_excludes_password(mock_family_repo, mock_user_repo):
	family = await mock_family_repo.save(Family(id=uuid4(), name="The Smiths", description="Test family"))
	user = User(
		family_id=family.id,
		email="jane@example.com",
		password_hash=pwd_context.hash("whatever"),
		full_name="Jane Smith",
		role="admin",
	)
	await mock_user_repo.save(user)

	use_case = ExportFamilyDataUseCase(mock_family_repo, mock_user_repo)
	result = await use_case.execute(ExportFamilyDataInput(family_id=family.id))

	assert result.family_name == "The Smiths"
	assert result.family_description == "Test family"
	assert len(result.users) == 1
	exported = result.users[0]
	assert exported.email == "jane@example.com"
	assert not hasattr(exported, "password_hash")


@pytest.mark.asyncio
async def test_export_family_data_family_not_found(mock_family_repo, mock_user_repo):
	use_case = ExportFamilyDataUseCase(mock_family_repo, mock_user_repo)
	with pytest.raises(LookupError):
		await use_case.execute(ExportFamilyDataInput(family_id=uuid4()))


@pytest.mark.asyncio
async def test_import_users_matches_existing_email_without_reinviting(
	mock_user_repo, mock_password_reset_token_repo, fake_email_sender
):
	family_id = uuid4()
	existing = await mock_user_repo.save(
		User(
			family_id=family_id,
			email="jane@example.com",
			password_hash=pwd_context.hash("their_real_password"),
			full_name="Jane Smith",
			role="admin",
		)
	)

	create_user = CreateUserUseCase(mock_user_repo, mock_password_reset_token_repo, fake_email_sender)
	update_user = UpdateUserUseCase(mock_user_repo)
	use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

	old_id = uuid4()
	result = await use_case.execute(
		ImportUsersInput(
			family_id=family_id,
			users=[ImportUserItem(id=old_id, email="jane@example.com", full_name="Jane Smith", role="admin")],
		)
	)

	assert result.matched == 1
	assert result.created == 0
	assert result.user_id_map[old_id] == existing.id
	# No invite email sent for a matched (already-existing) user.
	assert fake_email_sender.sent == []
	# The existing password must survive the import untouched.
	reloaded = await mock_user_repo.find_by_id(existing.id)
	assert pwd_context.verify("their_real_password", reloaded.password_hash)


@pytest.mark.asyncio
async def test_import_users_invites_unknown_email_and_applies_preferences(
	mock_user_repo, mock_password_reset_token_repo, fake_email_sender
):
	family_id = uuid4()
	create_user = CreateUserUseCase(mock_user_repo, mock_password_reset_token_repo, fake_email_sender)
	update_user = UpdateUserUseCase(mock_user_repo)
	use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

	old_id = uuid4()
	result = await use_case.execute(
		ImportUsersInput(
			family_id=family_id,
			users=[
				ImportUserItem(
					id=old_id,
					email="newbie@example.com",
					full_name="New Bie",
					role="viewer",
					is_active=True,
					annual_reading_goal=12,
					language="it",
					theme_name="akabeni",
					theme_mode="dark",
				)
			],
		)
	)

	assert result.created == 1
	assert result.matched == 0
	new_id = result.user_id_map[old_id]
	assert new_id != old_id

	created = await mock_user_repo.find_by_id(new_id)
	assert created.family_id == family_id
	assert created.annual_reading_goal == 12
	assert created.language == "it"
	assert created.theme_name == "akabeni"
	assert created.theme_mode == "dark"

	# Invited exactly like a normal new-member invite: one email, a setup link, no chosen password.
	assert len(fake_email_sender.sent) == 1
	assert fake_email_sender.sent[0]["purpose"] == "invite"


@pytest.mark.asyncio
async def test_import_users_mixed_batch_builds_correct_id_map(
	mock_user_repo, mock_password_reset_token_repo, fake_email_sender
):
	family_id = uuid4()
	existing = await mock_user_repo.save(
		User(
			family_id=family_id,
			email="existing@example.com",
			password_hash=pwd_context.hash("x"),
			full_name="Existing",
			role="editor",
		)
	)

	create_user = CreateUserUseCase(mock_user_repo, mock_password_reset_token_repo, fake_email_sender)
	update_user = UpdateUserUseCase(mock_user_repo)
	use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

	old_existing_id = uuid4()
	old_new_id = uuid4()
	result = await use_case.execute(
		ImportUsersInput(
			family_id=family_id,
			users=[
				ImportUserItem(id=old_existing_id, email="existing@example.com", full_name="Existing", role="editor"),
				ImportUserItem(id=old_new_id, email="brandnew@example.com", full_name="Brand New", role="viewer"),
			],
		)
	)

	assert result.matched == 1
	assert result.created == 1
	assert result.user_id_map[old_existing_id] == existing.id
	assert result.user_id_map[old_new_id] not in (existing.id, old_new_id)
	assert len(fake_email_sender.sent) == 1  # only the genuinely new one


@pytest.mark.asyncio
async def test_import_users_invites_a_removed_member_recovered_via_snapshot(
	mock_user_repo, mock_password_reset_token_repo, fake_email_sender
):
	"""A 'user' entry recovered from catalog-service's removed-member snapshot
	(real email/full_name/role captured when they were originally deleted)
	must go through the exact same match-or-invite path as a normal roster
	entry — no special-casing, no synthetic placeholder."""
	family_id = uuid4()
	create_user = CreateUserUseCase(mock_user_repo, mock_password_reset_token_repo, fake_email_sender)
	update_user = UpdateUserUseCase(mock_user_repo)
	use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

	recovered_id = uuid4()
	result = await use_case.execute(
		ImportUsersInput(
			family_id=family_id,
			users=[
				ImportUserItem(id=recovered_id, email="giuseppe@example.com", full_name="Giuseppe Bianchi", role="viewer")
			],
		)
	)

	assert result.created == 1
	new_id = result.user_id_map[recovered_id]
	recreated = await mock_user_repo.find_by_id(new_id)
	assert recreated.email == "giuseppe@example.com"
	assert recreated.full_name == "Giuseppe Bianchi"
	assert len(fake_email_sender.sent) == 1
