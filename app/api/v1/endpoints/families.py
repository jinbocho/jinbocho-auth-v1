from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_payload, get_db, require_role
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
from app.infrastructure.repositories import SQLAlchemyFamilyRepository, SQLAlchemyUserRepository

router = APIRouter()


@router.get(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Get family information",
    description="Get family information. Any authenticated member of the family."
)
async def get_family(
    family_id: UUID,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    family_repo = SQLAlchemyFamilyRepository(db)
    use_case = GetFamilyUseCase(family_repo)
    try:
        result = await use_case.execute(
            GetFamilyInput(family_id=family_id, requester_family_id=UUID(payload["family_id"]))
        )
        return FamilyResponse(**result.__dict__)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another family")
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")


@router.patch(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Update family information",
    description="Update family information. Can only update own family. Requires admin role."
)
async def update_family(
    family_id: UUID,
    request: FamilyUpdate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    family_repo = SQLAlchemyFamilyRepository(db)
    use_case = UpdateFamilyUseCase(family_repo)
    try:
        result = await use_case.execute(
            UpdateFamilyInput(
                family_id=family_id,
                requester_family_id=UUID(payload["family_id"]),
                name=request.name,
                description=request.description,
            )
        )
        await db.commit()
        return FamilyResponse(**result.__dict__)
    except PermissionError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another family")
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")


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
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if family_id != UUID(payload["family_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another family")
    family_repo = SQLAlchemyFamilyRepository(db)
    user_repo = SQLAlchemyUserRepository(db)
    use_case = ConfirmFamilyDeletionUseCase(family_repo, user_repo)
    try:
        await use_case.execute(
            VerifyFamilyDeletionInput(
                family_id=family_id,
                requester_id=UUID(payload["sub"]),
                password=request.password,
                confirm_family_name=request.confirm_family_name,
            )
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Family name does not match")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")


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
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if family_id != UUID(payload["family_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another family")
    family_repo = SQLAlchemyFamilyRepository(db)
    user_repo = SQLAlchemyUserRepository(db)
    use_case = DeleteFamilyUseCase(family_repo, user_repo)
    try:
        await use_case.execute(
            DeleteFamilyInput(
                family_id=family_id,
                requester_id=UUID(payload["sub"]),
                password=request.password,
                confirm_family_name=request.confirm_family_name,
            )
        )
        await db.commit()
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Family name does not match")
    except PermissionError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
