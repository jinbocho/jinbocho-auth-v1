import pytest
from uuid import uuid4

from app.application.use_cases.context import (
    ListMyLibrariesInput,
    ListMyLibrariesUseCase,
    SelectLibraryContextInput,
    SelectLibraryContextUseCase,
)
from app.application.use_cases.memberships import (
    AcceptInvitationInput,
    AcceptInvitationUseCase,
    DeclineInvitationInput,
    DeclineInvitationUseCase,
    GetMemberInput,
    GetMemberUseCase,
    InviteMemberInput,
    InviteMemberUseCase,
    ListMembersInput,
    ListMembersUseCase,
    RemoveMembershipInput,
    RemoveMembershipUseCase,
    SearchMembersInput,
    SearchMembersUseCase,
    UpdateMembershipInput,
    UpdateMembershipUseCase,
)
from app.domain.entities import Library, LibraryMembership, MembershipStatus, User, UserRole
from app.domain.exceptions import EntityNotFoundError, LastAdminError, NotAMemberError


async def _user(mock_user_repo, password_hasher, email="user@example.com", **overrides):
    user = User(
        id=uuid4(),
        library_id=overrides.pop("library_id", uuid4()),
        email=email,
        password_hash=password_hasher.hash("whatever"),
        full_name=overrides.pop("full_name", "Test User"),
        role=overrides.pop("role", UserRole.ADMIN),
        **overrides,
    )
    return await mock_user_repo.save(user)


@pytest.mark.asyncio
async def test_select_library_context_succeeds_for_active_membership(
    mock_user_repo, mock_membership_repo, password_hasher, token_service
):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher)
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.EDITOR, status=MembershipStatus.ACTIVE)
    )

    use_case = SelectLibraryContextUseCase(mock_user_repo, mock_membership_repo, token_service)
    result = await use_case.execute(SelectLibraryContextInput(user_id=user.id, library_id=library_id))

    assert result.library_id == library_id
    assert result.role == UserRole.EDITOR
    reloaded = await mock_user_repo.find_by_id(user.id)
    assert reloaded.last_selected_library_id == library_id


@pytest.mark.asyncio
async def test_select_library_context_rejects_non_member(mock_user_repo, mock_membership_repo, password_hasher, token_service):
    user = await _user(mock_user_repo, password_hasher)
    use_case = SelectLibraryContextUseCase(mock_user_repo, mock_membership_repo, token_service)

    with pytest.raises(NotAMemberError):
        await use_case.execute(SelectLibraryContextInput(user_id=user.id, library_id=uuid4()))


@pytest.mark.asyncio
async def test_select_library_context_rejects_revoked_membership(
    mock_user_repo, mock_membership_repo, password_hasher, token_service
):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher)
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.REVOKED)
    )

    use_case = SelectLibraryContextUseCase(mock_user_repo, mock_membership_repo, token_service)
    with pytest.raises(NotAMemberError):
        await use_case.execute(SelectLibraryContextInput(user_id=user.id, library_id=library_id))


@pytest.mark.asyncio
async def test_list_my_libraries_excludes_revoked(mock_user_repo, mock_membership_repo, mock_library_repo, password_hasher):
    user = await _user(mock_user_repo, password_hasher)
    active_library = await mock_library_repo.save(Library(id=uuid4(), name="Active Lib"))
    revoked_library = await mock_library_repo.save(Library(id=uuid4(), name="Revoked Lib"))
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=active_library.id, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=revoked_library.id, role=UserRole.VIEWER, status=MembershipStatus.REVOKED)
    )

    use_case = ListMyLibrariesUseCase(mock_membership_repo, mock_library_repo)
    result = await use_case.execute(ListMyLibrariesInput(user_id=user.id))

    assert len(result.libraries) == 1
    assert result.libraries[0].library_id == active_library.id


@pytest.mark.asyncio
async def test_invite_member_creates_pending_membership_for_existing_user(
    mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
    fake_email_sender, password_hasher, token_service,
):
    existing = await _user(mock_user_repo, password_hasher, email="existing@example.com")
    inviter = await _user(mock_user_repo, password_hasher, email="inviter@example.com")
    other_library = await mock_library_repo.save(Library(id=uuid4(), name="Other Library"))

    use_case = InviteMemberUseCase(
        mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
        fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    result = await use_case.execute(
        InviteMemberInput(
            library_id=other_library.id, invited_by=inviter.id, email=existing.email, full_name=None, role=UserRole.EDITOR
        )
    )

    assert result.is_new_account is False
    assert result.status == MembershipStatus.INVITED
    membership = await mock_membership_repo.find_by_user_and_library(existing.id, other_library.id)
    assert membership is not None
    assert membership.status == MembershipStatus.INVITED
    # No password-setup email — they already have an account — but a plain
    # notification telling them who invited them and where.
    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["purpose"] == "library_invite"
    assert fake_email_sender.sent[0]["to_email"] == existing.email
    assert fake_email_sender.sent[0]["library_name"] == "Other Library"
    assert fake_email_sender.sent[0]["inviter_name"] == inviter.full_name


@pytest.mark.asyncio
async def test_invite_member_creates_new_account_and_active_membership(
    mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
    fake_email_sender, password_hasher, token_service,
):
    library_id = uuid4()
    use_case = InviteMemberUseCase(
        mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
        fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    result = await use_case.execute(
        InviteMemberInput(library_id=library_id, invited_by=uuid4(), email="brandnew@example.com", full_name="Brand New", role=UserRole.VIEWER)
    )

    assert result.is_new_account is True
    assert result.status == MembershipStatus.ACTIVE
    assert len(fake_email_sender.sent) == 1
    assert fake_email_sender.sent[0]["purpose"] == "invite"


@pytest.mark.asyncio
async def test_accept_invitation_activates_membership(mock_membership_repo):
    user_id, library_id = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.INVITED)
    )
    use_case = AcceptInvitationUseCase(mock_membership_repo)
    await use_case.execute(AcceptInvitationInput(user_id=user_id, library_id=library_id))

    membership = await mock_membership_repo.find_by_user_and_library(user_id, library_id)
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.joined_at is not None


@pytest.mark.asyncio
async def test_decline_invitation_revokes_membership(mock_membership_repo):
    user_id, library_id = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.INVITED)
    )
    use_case = DeclineInvitationUseCase(mock_membership_repo)
    await use_case.execute(DeclineInvitationInput(user_id=user_id, library_id=library_id))

    membership = await mock_membership_repo.find_by_user_and_library(user_id, library_id)
    assert membership.status == MembershipStatus.REVOKED


@pytest.mark.asyncio
async def test_decline_invitation_rejects_when_no_pending_invite(mock_membership_repo):
    use_case = DeclineInvitationUseCase(mock_membership_repo)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(DeclineInvitationInput(user_id=uuid4(), library_id=uuid4()))


@pytest.mark.asyncio
async def test_declined_invitation_can_be_re_invited(
    mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
    fake_email_sender, password_hasher, token_service,
):
    existing = await _user(mock_user_repo, password_hasher, email="existing@example.com")
    inviter = await _user(mock_user_repo, password_hasher, email="inviter@example.com")
    library = await mock_library_repo.save(Library(id=uuid4(), name="Some Library"))
    await mock_membership_repo.save(
        LibraryMembership(user_id=existing.id, library_id=library.id, role=UserRole.VIEWER, status=MembershipStatus.INVITED)
    )
    decline_use_case = DeclineInvitationUseCase(mock_membership_repo)
    await decline_use_case.execute(DeclineInvitationInput(user_id=existing.id, library_id=library.id))

    invite_use_case = InviteMemberUseCase(
        mock_user_repo, mock_membership_repo, mock_library_repo, mock_password_reset_token_repo,
        fake_email_sender, token_service, password_hasher,
        invite_expire_minutes=10080, frontend_base_url="http://localhost:5173",
    )
    result = await invite_use_case.execute(
        InviteMemberInput(library_id=library.id, invited_by=inviter.id, email=existing.email, full_name=None, role=UserRole.EDITOR)
    )
    assert result.status == MembershipStatus.INVITED


@pytest.mark.asyncio
async def test_list_members_returns_roster_via_membership(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher, email="member@example.com")
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.EDITOR, status=MembershipStatus.ACTIVE)
    )

    use_case = ListMembersUseCase(mock_membership_repo, mock_user_repo)
    result = await use_case.execute(ListMembersInput(library_id=library_id))

    assert len(result.members) == 1
    assert result.members[0].email == "member@example.com"
    assert result.members[0].role == UserRole.EDITOR


@pytest.mark.asyncio
async def test_get_member_returns_profile_for_active_member(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher, email="member@example.com", full_name="Jane Member")
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
    )

    use_case = GetMemberUseCase(mock_membership_repo, mock_user_repo)
    result = await use_case.execute(GetMemberInput(library_id=library_id, user_id=user.id))

    assert result.full_name == "Jane Member"
    assert result.email == "member@example.com"
    assert result.role == UserRole.VIEWER


@pytest.mark.asyncio
async def test_get_member_rejects_non_member(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher, email="stranger@example.com")

    use_case = GetMemberUseCase(mock_membership_repo, mock_user_repo)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(GetMemberInput(library_id=library_id, user_id=user.id))


@pytest.mark.asyncio
async def test_get_member_rejects_invited_not_yet_active(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    user = await _user(mock_user_repo, password_hasher, email="pending@example.com")
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.INVITED)
    )

    use_case = GetMemberUseCase(mock_membership_repo, mock_user_repo)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(GetMemberInput(library_id=library_id, user_id=user.id))


@pytest.mark.asyncio
async def test_search_members_matches_name_or_email(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    alice = await _user(mock_user_repo, password_hasher, email="alice@example.com", full_name="Alice Rossi")
    bob = await _user(mock_user_repo, password_hasher, email="bob@example.com", full_name="Bob Verdi")
    for user in (alice, bob):
        await mock_membership_repo.save(
            LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
        )

    use_case = SearchMembersUseCase(mock_membership_repo, mock_user_repo)

    by_name = await use_case.execute(SearchMembersInput(library_id=library_id, query="ali"))
    assert [r.email for r in by_name.results] == ["alice@example.com"]

    by_email = await use_case.execute(SearchMembersInput(library_id=library_id, query="bob@"))
    assert [r.email for r in by_email.results] == ["bob@example.com"]


@pytest.mark.asyncio
async def test_search_members_ignores_other_libraries_and_inactive(mock_membership_repo, mock_user_repo, password_hasher):
    library_id, other_library_id = uuid4(), uuid4()
    in_this_library = await _user(mock_user_repo, password_hasher, email="here@example.com", full_name="Marco Bianchi")
    in_other_library = await _user(mock_user_repo, password_hasher, email="elsewhere@example.com", full_name="Marco Neri")
    suspended = await _user(mock_user_repo, password_hasher, email="suspended@example.com", full_name="Marco Gialli")
    await mock_membership_repo.save(
        LibraryMembership(user_id=in_this_library.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=in_other_library.id, library_id=other_library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=suspended.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.SUSPENDED)
    )

    use_case = SearchMembersUseCase(mock_membership_repo, mock_user_repo)
    result = await use_case.execute(SearchMembersInput(library_id=library_id, query="marco"))

    assert [r.email for r in result.results] == ["here@example.com"]


@pytest.mark.asyncio
async def test_search_members_requires_minimum_query_length(mock_membership_repo, mock_user_repo):
    use_case = SearchMembersUseCase(mock_membership_repo, mock_user_repo)
    result = await use_case.execute(SearchMembersInput(library_id=uuid4(), query="a"))
    assert result.results == []


@pytest.mark.asyncio
async def test_search_members_respects_limit(mock_membership_repo, mock_user_repo, password_hasher):
    library_id = uuid4()
    for i in range(5):
        user = await _user(mock_user_repo, password_hasher, email=f"person{i}@example.com", full_name=f"Person {i}")
        await mock_membership_repo.save(
            LibraryMembership(user_id=user.id, library_id=library_id, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
        )

    use_case = SearchMembersUseCase(mock_membership_repo, mock_user_repo)
    result = await use_case.execute(SearchMembersInput(library_id=library_id, query="person", limit=3))
    assert len(result.results) == 3


@pytest.mark.asyncio
async def test_update_membership_blocks_demoting_last_admin(mock_membership_repo):
    user_id, library_id = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_id, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    use_case = UpdateMembershipUseCase(mock_membership_repo)

    with pytest.raises(LastAdminError):
        await use_case.execute(UpdateMembershipInput(library_id=library_id, target_user_id=user_id, role=UserRole.EDITOR))


@pytest.mark.asyncio
async def test_update_membership_allows_demoting_admin_with_another_admin_present(mock_membership_repo):
    library_id = uuid4()
    user_id, other_admin_id = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_id, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=other_admin_id, library_id=library_id, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    use_case = UpdateMembershipUseCase(mock_membership_repo)
    await use_case.execute(UpdateMembershipInput(library_id=library_id, target_user_id=user_id, role=UserRole.EDITOR))

    membership = await mock_membership_repo.find_by_user_and_library(user_id, library_id)
    assert membership.role == UserRole.EDITOR


@pytest.mark.asyncio
async def test_remove_membership_blocks_removing_last_admin(mock_membership_repo):
    user_id, library_id = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_id, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    use_case = RemoveMembershipUseCase(mock_membership_repo)

    with pytest.raises(LastAdminError):
        await use_case.execute(RemoveMembershipInput(library_id=library_id, target_user_id=user_id))


@pytest.mark.asyncio
async def test_remove_membership_revokes_without_touching_other_libraries(mock_membership_repo):
    user_id = uuid4()
    library_a, library_b = uuid4(), uuid4()
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_a, role=UserRole.VIEWER, status=MembershipStatus.ACTIVE)
    )
    await mock_membership_repo.save(
        LibraryMembership(user_id=user_id, library_id=library_b, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE)
    )
    use_case = RemoveMembershipUseCase(mock_membership_repo)
    await use_case.execute(RemoveMembershipInput(library_id=library_a, target_user_id=user_id))

    revoked = await mock_membership_repo.find_by_user_and_library(user_id, library_a)
    untouched = await mock_membership_repo.find_by_user_and_library(user_id, library_b)
    assert revoked.status == MembershipStatus.REVOKED
    assert untouched.status == MembershipStatus.ACTIVE
