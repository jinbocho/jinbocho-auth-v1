import pytest
from uuid import uuid4

from app.application.use_cases.users import (
    DeleteUserInput,
    DeleteUserUseCase,
    UpdateUserInput,
    UpdateUserUseCase,
)
from app.domain.entities import LibraryMembership, MembershipStatus, User, UserRole
from app.domain.exceptions import LastAdminError


async def _make_user(mock_user_repo, library_id, role, *, is_active=True):
    user = User(
        library_id=library_id,
        email=f"{role}-{uuid4()}@example.com",
        password_hash="hash",
        full_name=role.title() if isinstance(role, str) else role.value.title(),
        role=UserRole(role),
        is_active=is_active,
    )
    return await mock_user_repo.save(user)


async def _make_user_and_membership(mock_user_repo, mock_membership_repo, library_id, role, *, is_active=True):
    user = await _make_user(mock_user_repo, library_id, role, is_active=is_active)
    await mock_membership_repo.save(
        LibraryMembership(
            user_id=user.id, library_id=library_id, role=UserRole(role),
            status=MembershipStatus.ACTIVE if is_active else MembershipStatus.SUSPENDED,
        )
    )
    return user


@pytest.mark.asyncio
async def test_cannot_demote_sole_admin(mock_user_repo, mock_membership_repo):
    library_id = uuid4()
    admin = await _make_user_and_membership(mock_user_repo, mock_membership_repo, library_id, "admin")

    use_case = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    with pytest.raises(LastAdminError):
        await use_case.execute(
            UpdateUserInput(user_id=admin.id, requester_library_id=library_id, role="viewer")
        )


@pytest.mark.asyncio
async def test_cannot_deactivate_sole_admin(mock_user_repo, mock_membership_repo):
    library_id = uuid4()
    admin = await _make_user_and_membership(mock_user_repo, mock_membership_repo, library_id, "admin")

    use_case = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    with pytest.raises(LastAdminError):
        await use_case.execute(
            UpdateUserInput(user_id=admin.id, requester_library_id=library_id, is_active=False)
        )


@pytest.mark.asyncio
async def test_cannot_delete_sole_admin(mock_user_repo):
    library_id = uuid4()
    admin = await _make_user(mock_user_repo, library_id, "admin")

    use_case = DeleteUserUseCase(mock_user_repo)
    with pytest.raises(LastAdminError):
        await use_case.execute(DeleteUserInput(user_id=admin.id, requester_library_id=library_id))


@pytest.mark.asyncio
async def test_can_demote_admin_when_another_active_admin_exists(mock_user_repo, mock_membership_repo):
    library_id = uuid4()
    admin = await _make_user_and_membership(mock_user_repo, mock_membership_repo, library_id, "admin")
    await _make_user_and_membership(mock_user_repo, mock_membership_repo, library_id, "admin")

    use_case = UpdateUserUseCase(mock_user_repo, mock_membership_repo)
    result = await use_case.execute(
        UpdateUserInput(user_id=admin.id, requester_library_id=library_id, role="viewer")
    )
    assert result.role == "viewer"


@pytest.mark.asyncio
async def test_can_delete_sole_admin_when_other_admin_is_inactive_is_still_blocked(mock_user_repo):
    """An inactive admin doesn't count as a fallback — only an active one does."""
    library_id = uuid4()
    admin = await _make_user(mock_user_repo, library_id, "admin")
    await _make_user(mock_user_repo, library_id, "admin", is_active=False)

    use_case = DeleteUserUseCase(mock_user_repo)
    with pytest.raises(LastAdminError):
        await use_case.execute(DeleteUserInput(user_id=admin.id, requester_library_id=library_id))


@pytest.mark.asyncio
async def test_can_delete_non_admin_user_freely(mock_user_repo):
    library_id = uuid4()
    await _make_user(mock_user_repo, library_id, "admin")
    viewer = await _make_user(mock_user_repo, library_id, "viewer")

    use_case = DeleteUserUseCase(mock_user_repo)
    await use_case.execute(DeleteUserInput(user_id=viewer.id, requester_library_id=library_id))
    assert await mock_user_repo.find_by_id(viewer.id) is None
