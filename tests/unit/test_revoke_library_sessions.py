import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.application.use_cases.libraries import RevokeLibrarySessionsInput, RevokeLibrarySessionsUseCase
from app.domain.entities import Library, RefreshToken, User, UserRole
from app.domain.exceptions import ForbiddenError


@pytest.fixture
def library_with_members(mock_library_repo, mock_user_repo):
    async def _create(member_count: int = 2):
        library = await mock_library_repo.save(Library(id=uuid4(), name="The Smiths", description=None))
        members = []
        for i in range(member_count):
            member = await mock_user_repo.save(
                User(
                    library_id=library.id,
                    email=f"member{i}@example.com",
                    password_hash="hash",
                    full_name=f"Member {i}",
                    role=UserRole.ADMIN if i == 0 else UserRole.EDITOR,
                )
            )
            members.append(member)
        return library, members

    return _create


@pytest.mark.asyncio
async def test_revoke_library_sessions_revokes_every_member_token(
    mock_library_repo, mock_user_repo, mock_refresh_token_repo, library_with_members
):
    library, members = await library_with_members(2)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    for member in members:
        await mock_refresh_token_repo.save(RefreshToken(user_id=member.id, token_hash=f"hash-{member.id}", expires_at=future))

    use_case = RevokeLibrarySessionsUseCase(mock_user_repo, mock_refresh_token_repo)
    result = await use_case.execute(RevokeLibrarySessionsInput(library_id=library.id, requester_library_id=library.id))

    assert result.revoked_count == 2
    for token in mock_refresh_token_repo.tokens.values():
        assert token.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_library_sessions_does_not_touch_other_libraries(
    mock_library_repo, mock_user_repo, mock_refresh_token_repo, library_with_members
):
    library_a, members_a = await library_with_members(1)
    library_b, members_b = await library_with_members(1)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    await mock_refresh_token_repo.save(
        RefreshToken(user_id=members_a[0].id, token_hash="hash-a", expires_at=future)
    )
    await mock_refresh_token_repo.save(
        RefreshToken(user_id=members_b[0].id, token_hash="hash-b", expires_at=future)
    )

    use_case = RevokeLibrarySessionsUseCase(mock_user_repo, mock_refresh_token_repo)
    result = await use_case.execute(RevokeLibrarySessionsInput(library_id=library_a.id, requester_library_id=library_a.id))

    assert result.revoked_count == 1
    assert mock_refresh_token_repo.tokens["hash-a"].revoked_at is not None
    assert mock_refresh_token_repo.tokens["hash-b"].revoked_at is None


@pytest.mark.asyncio
async def test_revoke_library_sessions_rejects_cross_library_request(
    mock_user_repo, mock_refresh_token_repo, library_with_members
):
    library, _ = await library_with_members(1)
    use_case = RevokeLibrarySessionsUseCase(mock_user_repo, mock_refresh_token_repo)

    with pytest.raises(ForbiddenError):
        await use_case.execute(RevokeLibrarySessionsInput(library_id=library.id, requester_library_id=uuid4()))
