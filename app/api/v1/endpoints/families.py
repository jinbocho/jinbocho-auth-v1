from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_user_payload,
    get_family_repository,
    get_password_hasher,
    get_user_repository,
    require_role,
)
from app.api.v1.schemas.family_schemas import DeleteFamilyRequest, FamilyResponse, FamilyUpdate
from app.application.use_cases.families import (
    ConfirmFamilyDeletionUseCase,
    DeleteFamilyInput,
    DeleteFamilyUseCase,
    GetFamilyUseCase,
    GetFamilyInput,
    UpdateFamilyUseCase,
    UpdateFamilyInput,
    VerifyFamilyDeletionInput,
)
from app.domain.repositories import FamilyRepository, UserRepository
from app.domain.services import PasswordHasher

router = APIRouter()


@router.get(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Get family information",
    description="Get family information. Any authenticated member of the family."
)
async def get_family(
    family_id: UUID,
    payload: dict[str, Any] = Depends(get_current_user_payload),
    family_repo: FamilyRepository = Depends(get_family_repository),
) -> FamilyResponse:
    use_case = GetFamilyUseCase(family_repo)
    result = await use_case.execute(
        GetFamilyInput(family_id=family_id, requester_family_id=UUID(payload["family_id"]))
    )
    return FamilyResponse(**result.__dict__)


@router.patch(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Update family information",
    description="Update family information. Can only update own family. Requires admin role."
)
async def update_family(
    family_id: UUID,
    request: FamilyUpdate,
    payload: dict[str, Any] = Depends(require_role("admin")),
    family_repo: FamilyRepository = Depends(get_family_repository),
) -> FamilyResponse:
    use_case = UpdateFamilyUseCase(family_repo)
    result = await use_case.execute(
        UpdateFamilyInput(
            family_id=family_id,
            requester_family_id=UUID(payload["family_id"]),
            name=request.name,
            description=request.description,
        )
    )
    return FamilyResponse(**result.__dict__)


@router.post(
    "/{family_id}/confirm-deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verify password + family name before deleting the account",
    description="Non-destructive preflight check for the irreversible full-account deletion — "
    "deletes nothing. Lets the frontend fail fast on a wrong password/name before it wipes the "
    "catalog-service library data, which must happen before DELETE /v1/families/{family_id}. "
    "Requires admin role."
)
async def confirm_family_deletion(
    family_id: UUID,
    request: DeleteFamilyRequest,
    payload: dict[str, Any] = Depends(require_role("admin")),
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> None:
    use_case = ConfirmFamilyDeletionUseCase(family_repo, user_repo, password_hasher)
    await use_case.execute(
        VerifyFamilyDeletionInput(
            family_id=family_id,
            requester_id=UUID(payload["sub"]),
            requester_family_id=UUID(payload["family_id"]),
            password=request.password,
            confirm_family_name=request.confirm_family_name,
        )
    )


@router.delete(
    "/{family_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the family and every one of its users",
    description="Irreversible. Cascades to every user, refresh token and password-reset token. "
    "The catalog-service library data is a separate database with no FK back to this one and is "
    "NOT touched by this call — the frontend must wipe it first (see GET /v1/catalog/export/full's "
    "sibling DELETE /v1/catalog/account), since a failure after this call would leave that data "
    "permanently orphaned with no account left able to reach it. Requires admin role and "
    "re-verifies password + family name itself, even if confirm-deletion already ran."
)
async def delete_family(
    family_id: UUID,
    request: DeleteFamilyRequest,
    payload: dict[str, Any] = Depends(require_role("admin")),
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> None:
    use_case = DeleteFamilyUseCase(family_repo, user_repo, password_hasher)
    await use_case.execute(
        DeleteFamilyInput(
            family_id=family_id,
            requester_id=UUID(payload["sub"]),
            requester_family_id=UUID(payload["family_id"]),
            password=request.password,
            confirm_family_name=request.confirm_family_name,
        )
    )
