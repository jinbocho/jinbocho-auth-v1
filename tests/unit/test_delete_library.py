import pytest
from uuid import uuid4

from app.application.use_cases.libraries import (
    ConfirmLibraryDeletionUseCase,
    DeleteLibraryInput,
    DeleteLibraryUseCase,
    VerifyLibraryDeletionInput,
)
from app.domain.entities import Library, User, UserRole


@pytest.fixture
def library_and_admin(mock_library_repo, mock_user_repo, password_hasher):
    async def _create():
        library = await mock_library_repo.save(Library(id=uuid4(), name="The Smiths", description=None))
        admin = await mock_user_repo.save(
            User(
                library_id=library.id,
                email="admin@example.com",
                password_hash=password_hasher.hash("correct-password"),
                full_name="Admin",
                role=UserRole.ADMIN,
            )
        )
        return library, admin

    return _create


@pytest.mark.asyncio
async def test_confirm_library_deletion_succeeds_with_correct_password_and_name(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    library, admin = await library_and_admin()
    use_case = ConfirmLibraryDeletionUseCase(mock_library_repo, mock_user_repo, password_hasher)

    await use_case.execute(
        VerifyLibraryDeletionInput(
            library_id=library.id,
            requester_id=admin.id,
            requester_library_id=library.id,
            password="correct-password",
            confirm_library_name="The Smiths",
        )
    )
    # Non-destructive: nothing was deleted.
    assert await mock_library_repo.find_by_id(library.id) is not None


@pytest.mark.asyncio
async def test_confirm_library_deletion_rejects_wrong_password(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    library, admin = await library_and_admin()
    use_case = ConfirmLibraryDeletionUseCase(mock_library_repo, mock_user_repo, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(
            VerifyLibraryDeletionInput(
                library_id=library.id,
                requester_id=admin.id,
                requester_library_id=library.id,
                password="wrong",
                confirm_library_name="The Smiths",
            )
        )


@pytest.mark.asyncio
async def test_confirm_library_deletion_rejects_wrong_library_name(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    library, admin = await library_and_admin()
    use_case = ConfirmLibraryDeletionUseCase(mock_library_repo, mock_user_repo, password_hasher)

    with pytest.raises(ValueError):
        await use_case.execute(
            VerifyLibraryDeletionInput(
                library_id=library.id,
                requester_id=admin.id,
                requester_library_id=library.id,
                password="correct-password",
                confirm_library_name="Wrong Name",
            )
        )


@pytest.mark.asyncio
async def test_delete_library_removes_the_library_when_verification_passes(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    library, admin = await library_and_admin()
    use_case = DeleteLibraryUseCase(mock_library_repo, mock_user_repo, password_hasher)

    await use_case.execute(
        DeleteLibraryInput(
            library_id=library.id,
            requester_id=admin.id,
            requester_library_id=library.id,
            password="correct-password",
            confirm_library_name="The Smiths",
        )
    )

    assert await mock_library_repo.find_by_id(library.id) is None


@pytest.mark.asyncio
async def test_delete_library_does_not_delete_on_wrong_password(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    """A stolen JWT alone must not be enough — the delete endpoint re-checks
    the password itself rather than trusting a prior confirm-deletion call."""
    library, admin = await library_and_admin()
    use_case = DeleteLibraryUseCase(mock_library_repo, mock_user_repo, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(
            DeleteLibraryInput(
                library_id=library.id,
                requester_id=admin.id,
                requester_library_id=library.id,
                password="wrong",
                confirm_library_name="The Smiths",
            )
        )

    assert await mock_library_repo.find_by_id(library.id) is not None


@pytest.mark.asyncio
async def test_delete_library_does_not_delete_on_wrong_library_name(
    mock_library_repo, mock_user_repo, library_and_admin, password_hasher
):
    library, admin = await library_and_admin()
    use_case = DeleteLibraryUseCase(mock_library_repo, mock_user_repo, password_hasher)

    with pytest.raises(ValueError):
        await use_case.execute(
            DeleteLibraryInput(
                library_id=library.id,
                requester_id=admin.id,
                requester_library_id=library.id,
                password="correct-password",
                confirm_library_name="Nope",
            )
        )

    assert await mock_library_repo.find_by_id(library.id) is not None
