import pytest
from uuid import uuid4

from app.application.use_cases.users import (
    CreateUserUseCase,
    ExportLibraryDataInput,
    ExportLibraryDataUseCase,
    ImportUserItem,
    ImportUsersInput,
    ImportUsersUseCase,
    UpdateUserUseCase,
)
from app.domain.entities import Library, User, UserRole
from app.domain.entities.enums import Language, ThemeMode, ThemeName


@pytest.mark.asyncio
async def test_export_library_data_excludes_password(mock_library_repo, mock_user_repo, password_hasher):
    library = await mock_library_repo.save(Library(id=uuid4(), name="The Smiths", description="Test library"))
    user = User(
        library_id=library.id,
        email="jane@example.com",
        password_hash=password_hasher.hash("whatever"),
        full_name="Jane Smith",
        role=UserRole.ADMIN,
    )
    await mock_user_repo.save(user)

    use_case = ExportLibraryDataUseCase(mock_library_repo, mock_user_repo)
    result = await use_case.execute(ExportLibraryDataInput(library_id=library.id))

    assert result.library_name == "The Smiths"
    assert result.library_description == "Test library"
    assert len(result.users) == 1
    exported = result.users[0]
    assert exported.email == "jane@example.com"
    assert not hasattr(exported, "password_hash")


@pytest.mark.asyncio
async def test_export_library_data_library_not_found(mock_library_repo, mock_user_repo):
    use_case = ExportLibraryDataUseCase(mock_library_repo, mock_user_repo)
    with pytest.raises(LookupError):
        await use_case.execute(ExportLibraryDataInput(library_id=uuid4()))


@pytest.mark.asyncio
async def test_import_users_matches_existing_email_without_reinviting(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    library_id = uuid4()
    existing = await mock_user_repo.save(
        User(
            library_id=library_id,
            email="jane@example.com",
            password_hash=password_hasher.hash("their_real_password"),
            full_name="Jane Smith",
            role=UserRole.ADMIN,
        )
    )

    create_user = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    update_user = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

    old_id = uuid4()
    result = await use_case.execute(
        ImportUsersInput(
            library_id=library_id,
            users=[ImportUserItem(id=old_id, email="jane@example.com", full_name="Jane Smith", role=UserRole.ADMIN)],
        )
    )

    assert result.matched == 1
    assert result.created == 0
    assert result.user_id_map[old_id] == existing.id
    assert fake_email_sender.sent == []
    reloaded = await mock_user_repo.find_by_id(existing.id)
    assert password_hasher.verify("their_real_password", reloaded.password_hash)


@pytest.mark.asyncio
async def test_import_users_invites_unknown_email_and_applies_preferences(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    library_id = uuid4()
    create_user = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    update_user = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

    old_id = uuid4()
    result = await use_case.execute(
        ImportUsersInput(
            library_id=library_id,
            users=[
                ImportUserItem(
                    id=old_id,
                    email="newbie@example.com",
                    full_name="New Bie",
                    role=UserRole.VIEWER,
                    is_active=True,
                    annual_reading_goal=12,
                    language=Language.IT,
                    theme_name=ThemeName.AKABENI,
                    theme_mode=ThemeMode.DARK,
                )
            ],
        )
    )

    assert result.created == 1
    assert result.matched == 0
    new_id = result.user_id_map[old_id]
    assert new_id != old_id

    created = await mock_user_repo.find_by_id(new_id)
    assert created.library_id == library_id
    assert created.annual_reading_goal == 12
    assert created.language == Language.IT
    assert created.theme_name == ThemeName.AKABENI
    assert created.theme_mode == ThemeMode.DARK

    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["purpose"] == "invite"


@pytest.mark.asyncio
async def test_import_users_mixed_batch_builds_correct_id_map(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    library_id = uuid4()
    existing = await mock_user_repo.save(
        User(
            library_id=library_id,
            email="existing@example.com",
            password_hash=password_hasher.hash("x"),
            full_name="Existing",
            role=UserRole.EDITOR,
        )
    )

    create_user = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    update_user = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

    old_existing_id = uuid4()
    old_new_id = uuid4()
    result = await use_case.execute(
        ImportUsersInput(
            library_id=library_id,
            users=[
                ImportUserItem(id=old_existing_id, email="existing@example.com", full_name="Existing", role=UserRole.EDITOR),
                ImportUserItem(id=old_new_id, email="brandnew@example.com", full_name="Brand New", role=UserRole.VIEWER),
            ],
        )
    )

    assert result.matched == 1
    assert result.created == 1
    assert result.user_id_map[old_existing_id] == existing.id
    assert result.user_id_map[old_new_id] not in (existing.id, old_new_id)
    assert len(fake_email_sender.sent) == 1


@pytest.mark.asyncio
async def test_import_users_invites_a_removed_member_recovered_via_snapshot(
    mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, password_hasher, token_service
):
    """A 'user' entry recovered from catalog-service's removed-member snapshot
    must go through the exact same match-or-invite path as a normal roster
    entry — no special-casing, no synthetic placeholder."""
    library_id = uuid4()
    create_user = CreateUserUseCase(
        mock_user_repo, mock_membership_repo, mock_password_reset_token_repo, fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    update_user = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    use_case = ImportUsersUseCase(mock_user_repo, create_user, update_user)

    recovered_id = uuid4()
    result = await use_case.execute(
        ImportUsersInput(
            library_id=library_id,
            users=[
                ImportUserItem(id=recovered_id, email="giuseppe@example.com", full_name="Giuseppe Bianchi", role=UserRole.VIEWER)
            ],
        )
    )

    assert result.created == 1
    new_id = result.user_id_map[recovered_id]
    recreated = await mock_user_repo.find_by_id(new_id)
    assert recreated.email == "giuseppe@example.com"
    assert recreated.full_name == "Giuseppe Bianchi"
    assert len(fake_email_sender.sent) == 1
