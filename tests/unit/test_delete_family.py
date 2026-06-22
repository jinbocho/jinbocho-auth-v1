import pytest
from uuid import uuid4

from app.application.use_cases.families import (
    ConfirmFamilyDeletionUseCase,
    DeleteFamilyInput,
    DeleteFamilyUseCase,
    VerifyFamilyDeletionInput,
)
from app.domain.entities import Family, User


@pytest.fixture
def family_and_admin(mock_family_repo, mock_user_repo, password_hasher):
    async def _create():
        family = await mock_family_repo.save(Family(id=uuid4(), name="The Smiths", description=None))
        admin = await mock_user_repo.save(
            User(
                family_id=family.id,
                email="admin@example.com",
                password_hash=password_hasher.hash("correct-password"),
                full_name="Admin",
                role="admin",
            )
        )
        return family, admin

    return _create


@pytest.mark.asyncio
async def test_confirm_family_deletion_succeeds_with_correct_password_and_name(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    family, admin = await family_and_admin()
    use_case = ConfirmFamilyDeletionUseCase(mock_family_repo, mock_user_repo, password_hasher)

    await use_case.execute(
        VerifyFamilyDeletionInput(
            family_id=family.id,
            requester_id=admin.id,
            requester_family_id=family.id,
            password="correct-password",
            confirm_family_name="The Smiths",
        )
    )
    # Non-destructive: nothing was deleted.
    assert await mock_family_repo.find_by_id(family.id) is not None


@pytest.mark.asyncio
async def test_confirm_family_deletion_rejects_wrong_password(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    family, admin = await family_and_admin()
    use_case = ConfirmFamilyDeletionUseCase(mock_family_repo, mock_user_repo, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(
            VerifyFamilyDeletionInput(
                family_id=family.id,
                requester_id=admin.id,
                requester_family_id=family.id,
                password="wrong",
                confirm_family_name="The Smiths",
            )
        )


@pytest.mark.asyncio
async def test_confirm_family_deletion_rejects_wrong_family_name(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    family, admin = await family_and_admin()
    use_case = ConfirmFamilyDeletionUseCase(mock_family_repo, mock_user_repo, password_hasher)

    with pytest.raises(ValueError):
        await use_case.execute(
            VerifyFamilyDeletionInput(
                family_id=family.id,
                requester_id=admin.id,
                requester_family_id=family.id,
                password="correct-password",
                confirm_family_name="Wrong Name",
            )
        )


@pytest.mark.asyncio
async def test_delete_family_removes_the_family_when_verification_passes(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    family, admin = await family_and_admin()
    use_case = DeleteFamilyUseCase(mock_family_repo, mock_user_repo, password_hasher)

    await use_case.execute(
        DeleteFamilyInput(
            family_id=family.id,
            requester_id=admin.id,
            requester_family_id=family.id,
            password="correct-password",
            confirm_family_name="The Smiths",
        )
    )

    assert await mock_family_repo.find_by_id(family.id) is None


@pytest.mark.asyncio
async def test_delete_family_does_not_delete_on_wrong_password(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    """A stolen JWT alone must not be enough — the delete endpoint re-checks
    the password itself rather than trusting a prior confirm-deletion call."""
    family, admin = await family_and_admin()
    use_case = DeleteFamilyUseCase(mock_family_repo, mock_user_repo, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(
            DeleteFamilyInput(
                family_id=family.id,
                requester_id=admin.id,
                requester_family_id=family.id,
                password="wrong",
                confirm_family_name="The Smiths",
            )
        )

    assert await mock_family_repo.find_by_id(family.id) is not None


@pytest.mark.asyncio
async def test_delete_family_does_not_delete_on_wrong_family_name(
    mock_family_repo, mock_user_repo, family_and_admin, password_hasher
):
    family, admin = await family_and_admin()
    use_case = DeleteFamilyUseCase(mock_family_repo, mock_user_repo, password_hasher)

    with pytest.raises(ValueError):
        await use_case.execute(
            DeleteFamilyInput(
                family_id=family.id,
                requester_id=admin.id,
                requester_family_id=family.id,
                password="correct-password",
                confirm_family_name="Nope",
            )
        )

    assert await mock_family_repo.find_by_id(family.id) is not None
