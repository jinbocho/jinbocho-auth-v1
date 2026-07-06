from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    JWTPayload,
    get_confirm_library_deletion_use_case,
    get_delete_library_use_case,
    get_get_library_use_case,
    get_revoke_library_sessions_use_case,
    get_update_library_use_case,
    require_library_context,
    require_role,
)
from app.api.v1.schemas.library_schemas import (
    DeleteLibraryRequest,
    LibraryResponse,
    LibraryUpdate,
    RevokeSessionsResponse,
)
from app.application.use_cases.libraries import (
    ConfirmLibraryDeletionUseCase,
    DeleteLibraryInput,
    DeleteLibraryUseCase,
    GetLibraryInput,
    GetLibraryUseCase,
    RevokeLibrarySessionsInput,
    RevokeLibrarySessionsUseCase,
    UpdateLibraryInput,
    UpdateLibraryUseCase,
    VerifyLibraryDeletionInput,
)

router = APIRouter()


@router.get(
    "/{library_id}",
    response_model=LibraryResponse,
    summary="Get library information",
    description="Get library information. Any authenticated member of the library."
)
async def get_library(
    library_id: UUID,
    payload: JWTPayload = Depends(require_library_context),
    use_case: GetLibraryUseCase = Depends(get_get_library_use_case),
) -> LibraryResponse:
    result = await use_case.execute(
        GetLibraryInput(library_id=library_id, requester_library_id=UUID(payload["library_id"]))
    )
    return LibraryResponse(**result.__dict__)


@router.patch(
    "/{library_id}",
    response_model=LibraryResponse,
    summary="Update library information",
    description="Update library information. Can only update own library. Requires admin role."
)
async def update_library(
    library_id: UUID,
    request: LibraryUpdate,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: UpdateLibraryUseCase = Depends(get_update_library_use_case),
) -> LibraryResponse:
    result = await use_case.execute(
        UpdateLibraryInput(
            library_id=library_id,
            requester_library_id=UUID(payload["library_id"]),
            name=request.name,
            description=request.description,
        )
    )
    return LibraryResponse(**result.__dict__)


@router.post(
    "/{library_id}/confirm-deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verify password + library name before deleting the account",
    description="Non-destructive preflight check for the irreversible full-account deletion — "
    "deletes nothing. Lets the frontend fail fast on a wrong password/name before it wipes the "
    "catalog-service library data, which must happen before DELETE /v1/libraries/{library_id}. "
    "Requires admin role."
)
async def confirm_library_deletion(
    library_id: UUID,
    request: DeleteLibraryRequest,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: ConfirmLibraryDeletionUseCase = Depends(get_confirm_library_deletion_use_case),
) -> None:
    await use_case.execute(
        VerifyLibraryDeletionInput(
            library_id=library_id,
            requester_id=UUID(payload["sub"]),
            requester_library_id=UUID(payload["library_id"]),
            password=request.password,
            confirm_library_name=request.confirm_library_name,
        )
    )


@router.post(
    "/{library_id}/revoke-sessions",
    response_model=RevokeSessionsResponse,
    summary="Emergency: revoke every active session for every library member",
    description="Revokes every refresh token for every member of the library, forcing everyone to "
    "log in again next time their access token expires or they try to refresh it. Use this if a "
    "credential leak is suspected. Already-issued access tokens keep working until their natural "
    "expiry (JWTs are stateless by design, ADR-008) — this bounds, but does not instantly close, "
    "the exposure window. Requires admin role."
)
async def revoke_library_sessions(
    library_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: RevokeLibrarySessionsUseCase = Depends(get_revoke_library_sessions_use_case),
) -> RevokeSessionsResponse:
    result = await use_case.execute(
        RevokeLibrarySessionsInput(library_id=library_id, requester_library_id=UUID(payload["library_id"]))
    )
    return RevokeSessionsResponse(revoked_count=result.revoked_count)


@router.delete(
    "/{library_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the library and every one of its users",
    description="Irreversible. Cascades to every user, refresh token and password-reset token. "
    "The catalog-service library data is a separate database with no FK back to this one and is "
    "NOT touched by this call — the frontend must wipe it first (see GET /v1/catalog/export/full's "
    "sibling DELETE /v1/catalog/account), since a failure after this call would leave that data "
    "permanently orphaned with no account left able to reach it. Requires admin role and "
    "re-verifies password + library name itself, even if confirm-deletion already ran."
)
async def delete_library(
    library_id: UUID,
    request: DeleteLibraryRequest,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: DeleteLibraryUseCase = Depends(get_delete_library_use_case),
) -> None:
    await use_case.execute(
        DeleteLibraryInput(
            library_id=library_id,
            requester_id=UUID(payload["sub"]),
            requester_library_id=UUID(payload["library_id"]),
            password=request.password,
            confirm_library_name=request.confirm_library_name,
        )
    )
