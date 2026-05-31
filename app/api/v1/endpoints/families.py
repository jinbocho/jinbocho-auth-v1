from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_role
from app.api.v1.schemas.family_schemas import FamilyResponse, FamilyUpdate
from app.application.use_cases.families import (
    GetFamilyUseCase,
    GetFamilyInput,
    UpdateFamilyUseCase,
    UpdateFamilyInput,
)
from app.infrastructure.repositories import SQLAlchemyFamilyRepository

router = APIRouter()


@router.get(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Get family information",
    description="Get family information. Can only access own family."
)
async def get_family(
    family_id: UUID,
    payload: dict = Depends(require_role("admin")),
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
