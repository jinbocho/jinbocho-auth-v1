from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    JWTPayload,
    get_accept_invitation_use_case,
    get_current_user_payload,
    get_decline_invitation_use_case,
    get_list_my_libraries_use_case,
    get_select_library_context_use_case,
)
from app.api.v1.schemas.context_schemas import ContextTokenResponse, LibrarySummaryResponse, SelectLibraryRequest
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
)

router = APIRouter()


@router.get(
    "/libraries",
    response_model=list[LibrarySummaryResponse],
    summary="List my libraries",
    description="List every library the caller is a member of (active, suspended, or with a "
    "pending invite). Works with a context-less token — this is the endpoint the frontend "
    "calls to render the post-login library picker."
)
async def list_my_libraries(
    payload: JWTPayload = Depends(get_current_user_payload),
    use_case: ListMyLibrariesUseCase = Depends(get_list_my_libraries_use_case),
) -> list[LibrarySummaryResponse]:
    result = await use_case.execute(ListMyLibrariesInput(user_id=UUID(payload["sub"])))
    return [
        LibrarySummaryResponse(
            library_id=lib.library_id, name=lib.name, role=lib.role.value, status=lib.status.value,
            last_accessed_at=lib.last_accessed_at,
        )
        for lib in result.libraries
    ]


@router.post(
    "/select",
    response_model=ContextTokenResponse,
    summary="Select active library",
    description="Mint a new access token scoped to the given library. Used both for the initial "
    "post-login choice and for later switches from the header. Requires an active membership; "
    "fails with 403 if the caller was removed from the library in the meantime.",
    responses={403: {"description": "Not an active member of this library"}},
)
async def select_library(
    request: SelectLibraryRequest,
    payload: JWTPayload = Depends(get_current_user_payload),
    use_case: SelectLibraryContextUseCase = Depends(get_select_library_context_use_case),
) -> ContextTokenResponse:
    result = await use_case.execute(
        SelectLibraryContextInput(user_id=UUID(payload["sub"]), library_id=request.library_id)
    )
    return ContextTokenResponse(access_token=result.access_token, library_id=result.library_id, role=result.role.value)


@router.post(
    "/libraries/{library_id}/accept",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Accept a pending library invitation",
    description="Turns a pending `invited` membership into `active`. Call POST /select "
    "afterwards to actually switch into it.",
)
async def accept_invitation(
    library_id: UUID,
    payload: JWTPayload = Depends(get_current_user_payload),
    use_case: AcceptInvitationUseCase = Depends(get_accept_invitation_use_case),
) -> None:
    await use_case.execute(AcceptInvitationInput(user_id=UUID(payload["sub"]), library_id=library_id))


@router.post(
    "/libraries/{library_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Decline a pending library invitation",
    description="Turns a pending `invited` membership into `revoked` — the same terminal state "
    "an admin-initiated removal ends in. An admin can invite the same email again later.",
)
async def decline_invitation(
    library_id: UUID,
    payload: JWTPayload = Depends(get_current_user_payload),
    use_case: DeclineInvitationUseCase = Depends(get_decline_invitation_use_case),
) -> None:
    await use_case.execute(DeclineInvitationInput(user_id=UUID(payload["sub"]), library_id=library_id))
