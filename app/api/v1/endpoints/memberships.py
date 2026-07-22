from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    JWTPayload,
    get_create_child_account_use_case,
    get_get_member_use_case,
    get_invite_member_use_case,
    get_list_members_use_case,
    get_list_membership_activity_use_case,
    get_remove_membership_use_case,
    get_search_members_use_case,
    get_update_membership_use_case,
    require_library_context,
    require_parent,
    require_role,
)
from app.api.v1.schemas.context_schemas import (
    ChildAccountResponse,
    CreateChildRequest,
    InviteMemberRequest,
    MembershipActivityResponse,
    MemberProfileResponse,
    MemberResponse,
    MemberSearchResultResponse,
    UpdateMembershipRequest,
)
from app.application.use_cases.children import CreateChildAccountInput, CreateChildAccountUseCase
from app.application.use_cases.memberships import (
    GetMemberInput,
    GetMemberUseCase,
    InviteMemberInput,
    InviteMemberUseCase,
    ListMembersInput,
    ListMembersUseCase,
    ListMembershipActivityInput,
    ListMembershipActivityUseCase,
    RemoveMembershipInput,
    RemoveMembershipUseCase,
    SearchMembersInput,
    SearchMembersUseCase,
    UpdateMembershipInput,
    UpdateMembershipUseCase,
)
from app.domain.entities import MembershipStatus, UserRole

router = APIRouter()


@router.get(
    "/{library_id}/members/search",
    response_model=list[MemberSearchResultResponse],
    summary="Typeahead search across this library's active members",
    description="Powers 'lend this book to a Jinbocho user' — any active member can search "
    "(not admin-only, unlike the full roster), since anyone can register a loan. Requires at "
    "least 2 characters; returns at most `limit` (default 3) results."
)
async def search_members(
    library_id: UUID,
    q: str,
    limit: int = 3,
    payload: JWTPayload = Depends(require_library_context),
    use_case: SearchMembersUseCase = Depends(get_search_members_use_case),
) -> list[MemberSearchResultResponse]:
    result = await use_case.execute(
        SearchMembersInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            query=q,
            limit=min(limit, 10),
        )
    )
    return [
        MemberSearchResultResponse(
            user_id=r.user_id, full_name=r.full_name, email=r.email, role=r.role.value, avatar_url=r.avatar_url,
        )
        for r in result.results
    ]


@router.get(
    "/{library_id}/members",
    response_model=list[MemberResponse],
    summary="List library members",
    description="Membership-based roster: includes members whose only relationship to this "
    "library is a membership row, not the legacy users.library_id scalar. Requires admin role."
)
async def list_members(
    library_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: ListMembersUseCase = Depends(get_list_members_use_case),
) -> list[MemberResponse]:
    result = await use_case.execute(
        ListMembersInput(library_id=library_id, requester_library_id=UUID(payload["library_id"]))
    )
    return [
        MemberResponse(
            membership_id=m.membership_id, user_id=m.user_id, email=m.email, full_name=m.full_name,
            role=m.role.value, status=m.status.value, joined_at=m.joined_at, last_accessed_at=m.last_accessed_at,
            avatar_url=m.avatar_url, birth_year=m.birth_year,
        )
        for m in result.members
    ]


@router.get(
    "/{library_id}/members/activity",
    response_model=list[MembershipActivityResponse],
    summary="Recent member-added/member-removed events for the dashboard activity feed",
    description="Open to any active member (unlike the full roster, which is admin-only). "
    "Registered before the /{user_id} route below so 'activity' is matched as a literal "
    "path segment rather than an attempted UUID."
)
async def get_membership_activity(
    library_id: UUID,
    limit: int = 20,
    payload: JWTPayload = Depends(require_library_context),
    use_case: ListMembershipActivityUseCase = Depends(get_list_membership_activity_use_case),
) -> list[MembershipActivityResponse]:
    result = await use_case.execute(
        ListMembershipActivityInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            limit=min(limit, 50),
        )
    )
    return [
        MembershipActivityResponse(
            user_id=i.user_id, full_name=i.full_name, avatar_url=i.avatar_url,
            role=i.role.value, event=i.event, occurred_at=i.occurred_at,
        )
        for i in result.items
    ]


@router.get(
    "/{library_id}/members/{user_id}",
    response_model=MemberProfileResponse,
    summary="Get a single member's basic profile",
    description="Open to any active member (unlike the full roster, which is admin-only) — "
    "powers viewing a fellow member's page, e.g. clicked from a loan's borrower name."
)
async def get_member(
    library_id: UUID,
    user_id: UUID,
    payload: JWTPayload = Depends(require_library_context),
    use_case: GetMemberUseCase = Depends(get_get_member_use_case),
) -> MemberProfileResponse:
    result = await use_case.execute(
        GetMemberInput(
            library_id=library_id, requester_library_id=UUID(payload["library_id"]), user_id=user_id
        )
    )
    return MemberProfileResponse(
        user_id=result.user_id, full_name=result.full_name, email=result.email,
        role=result.role.value, avatar_url=result.avatar_url, joined_at=result.joined_at,
        birth_year=result.birth_year,
    )


@router.post(
    "/{library_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member to this library",
    description="If the email already has an account (accounts are global), adds a pending "
    "membership to it — no new account or password flow. Otherwise creates a new account and "
    "emails a password-setup link, exactly like the legacy invite flow. Requires admin role."
)
async def invite_member(
    library_id: UUID,
    request: InviteMemberRequest,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: InviteMemberUseCase = Depends(get_invite_member_use_case),
) -> MemberResponse:
    result = await use_case.execute(
        InviteMemberInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            invited_by=UUID(payload["sub"]),
            email=request.email,
            full_name=request.full_name,
            role=UserRole(request.role),
        )
    )
    return MemberResponse(
        membership_id=result.membership_id, user_id=result.user_id, email=result.email,
        full_name=request.full_name or result.email, role=result.role.value, status=result.status.value,
    )


@router.post(
    "/{library_id}/members/children",
    response_model=ChildAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a self-service child account (kids mode only)",
    description="Creates a real, immediately-usable email+password account for a child, scoped "
    "to the CHILD role — no email is collected from the caller, a non-deliverable login "
    "identifier is generated and returned instead. Recovery emails (if ever needed) go to the "
    "creating parent's own email, not the child's. Requires kids mode enabled for this library "
    "and admin or editor role."
)
async def create_child_account(
    library_id: UUID,
    request: CreateChildRequest,
    payload: JWTPayload = Depends(require_parent),
    use_case: CreateChildAccountUseCase = Depends(get_create_child_account_use_case),
) -> ChildAccountResponse:
    result = await use_case.execute(
        CreateChildAccountInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            created_by=UUID(payload["sub"]),
            guardian_email=payload["email"],
            full_name=request.full_name,
            password=request.password,
            birth_year=request.birth_year,
        )
    )
    return ChildAccountResponse(
        user_id=result.user_id, membership_id=result.membership_id, full_name=result.full_name, email=result.email,
    )


@router.patch(
    "/{library_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change a member's role or suspend/reactivate them",
    description="Refuses to demote or suspend the library's last active admin. Requires admin role."
)
async def update_membership(
    library_id: UUID,
    user_id: UUID,
    request: UpdateMembershipRequest,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: UpdateMembershipUseCase = Depends(get_update_membership_use_case),
) -> None:
    await use_case.execute(
        UpdateMembershipInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            target_user_id=user_id,
            role=UserRole(request.role) if request.role else None,
            status=MembershipStatus(request.status) if request.status else None,
        )
    )


@router.delete(
    "/{library_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a member's access to this library",
    description="Soft-delete: the membership row is kept (status=revoked) for audit, the "
    "global user account is untouched. Refuses to remove the last active admin. Requires admin role."
)
async def remove_member(
    library_id: UUID,
    user_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: RemoveMembershipUseCase = Depends(get_remove_membership_use_case),
) -> None:
    await use_case.execute(
        RemoveMembershipInput(
            library_id=library_id, requester_library_id=UUID(payload["library_id"]), target_user_id=user_id
        )
    )
