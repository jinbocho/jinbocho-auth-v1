import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.application.use_cases.users import UpdateTourStatusInput, UpdateTourStatusUseCase
from app.domain.entities import LibraryMembership, MembershipStatus, UserRole
from app.domain.exceptions import EntityNotFoundError


@pytest.mark.asyncio
async def test_complete_tour_sets_timestamp(mock_user_repo, mock_membership_repo, test_user):
    await mock_user_repo.save(test_user)
    await mock_membership_repo.save(
        LibraryMembership(
            user_id=test_user.id, library_id=test_user.library_id, role=UserRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    use_case = UpdateTourStatusUseCase(mock_user_repo, mock_membership_repo)

    await use_case.execute(
        UpdateTourStatusInput(user_id=test_user.id, requester_library_id=test_user.library_id, completed=True)
    )

    saved = await mock_user_repo.find_by_id(test_user.id)
    assert saved.tour_completed_at is not None


@pytest.mark.asyncio
async def test_reset_tour_clears_timestamp(mock_user_repo, mock_membership_repo, test_user):
    test_user.tour_completed_at = datetime.now(timezone.utc)
    await mock_user_repo.save(test_user)
    await mock_membership_repo.save(
        LibraryMembership(
            user_id=test_user.id, library_id=test_user.library_id, role=UserRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
    )
    use_case = UpdateTourStatusUseCase(mock_user_repo, mock_membership_repo)

    await use_case.execute(
        UpdateTourStatusInput(user_id=test_user.id, requester_library_id=test_user.library_id, completed=False)
    )

    saved = await mock_user_repo.find_by_id(test_user.id)
    assert saved.tour_completed_at is None


@pytest.mark.asyncio
async def test_raises_when_user_not_found(mock_user_repo, mock_membership_repo):
    use_case = UpdateTourStatusUseCase(mock_user_repo, mock_membership_repo)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(
            UpdateTourStatusInput(user_id=uuid4(), requester_library_id=uuid4(), completed=True)
        )


@pytest.mark.asyncio
async def test_raises_when_membership_not_active(mock_user_repo, mock_membership_repo, test_user):
    await mock_user_repo.save(test_user)
    other_library_id = uuid4()
    use_case = UpdateTourStatusUseCase(mock_user_repo, mock_membership_repo)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(
            UpdateTourStatusInput(user_id=test_user.id, requester_library_id=other_library_id, completed=True)
        )
