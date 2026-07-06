import pytest
from uuid import uuid4

from app.application.use_cases.users import SearchUsersInput, SearchUsersUseCase
from app.domain.entities import LibraryMembership, MembershipStatus, User, UserRole


async def _user(mock_user_repo, password_hasher, email, full_name, is_active=True):
    user = User(
        library_id=uuid4(), email=email, password_hash=password_hasher.hash("whatever"),
        full_name=full_name, role=UserRole.VIEWER, is_active=is_active,
    )
    return await mock_user_repo.save(user)


@pytest.mark.asyncio
async def test_search_users_finds_match_by_name_or_email(mock_user_repo, password_hasher):
    library_id = uuid4()
    await _user(mock_user_repo, password_hasher, "alice@example.com", "Alice Rossi")
    await _user(mock_user_repo, password_hasher, "bob@example.com", "Bob Verdi")

    use_case = SearchUsersUseCase(mock_user_repo)
    result = await use_case.execute(
        SearchUsersInput(query="alice", exclude_library_id=library_id, requested_by=uuid4())
    )

    assert [r.email for r in result.results] == ["alice@example.com"]


@pytest.mark.asyncio
async def test_search_users_requires_minimum_four_characters(mock_user_repo, password_hasher):
    await _user(mock_user_repo, password_hasher, "alice@example.com", "Alice Rossi")

    use_case = SearchUsersUseCase(mock_user_repo)
    result = await use_case.execute(
        SearchUsersInput(query="ali", exclude_library_id=uuid4(), requested_by=uuid4())
    )

    assert result.results == []


@pytest.mark.asyncio
async def test_search_users_excludes_existing_non_revoked_members(
    mock_user_repo, mock_membership_repo, password_hasher
):
    library_id = uuid4()
    already_member = await _user(mock_user_repo, password_hasher, "marco.bianchi@example.com", "Marco Bianchi")
    stranger = await _user(mock_user_repo, password_hasher, "marco.neri@example.com", "Marco Neri")
    previously_removed = await _user(mock_user_repo, password_hasher, "marco.verdi@example.com", "Marco Verdi")
    await mock_membership_repo.save(
        LibraryMembership(user_id=already_member.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=previously_removed.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.REVOKED)
    )
    mock_user_repo.membership_repo = mock_membership_repo

    use_case = SearchUsersUseCase(mock_user_repo)
    result = await use_case.execute(
        SearchUsersInput(query="marco", exclude_library_id=library_id, requested_by=uuid4())
    )

    emails = {r.email for r in result.results}
    assert emails == {stranger.email, previously_removed.email}


@pytest.mark.asyncio
async def test_search_users_excludes_inactive_accounts(mock_user_repo, password_hasher):
    await _user(mock_user_repo, password_hasher, "gone@example.com", "Gone User", is_active=False)

    use_case = SearchUsersUseCase(mock_user_repo)
    result = await use_case.execute(
        SearchUsersInput(query="gone", exclude_library_id=uuid4(), requested_by=uuid4())
    )

    assert result.results == []


@pytest.mark.asyncio
async def test_search_users_respects_limit(mock_user_repo, password_hasher):
    for i in range(5):
        await _user(mock_user_repo, password_hasher, f"person{i}@example.com", f"Person {i}")

    use_case = SearchUsersUseCase(mock_user_repo)
    result = await use_case.execute(
        SearchUsersInput(query="person", exclude_library_id=uuid4(), requested_by=uuid4(), limit=3)
    )

    assert len(result.results) == 3
