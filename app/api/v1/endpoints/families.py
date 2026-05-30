from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import AsyncSession, get_db, require_role
from app.infrastructure.models import FamilyModel
from sqlalchemy import select

router = APIRouter()


class FamilyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None


class FamilyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("/{family_id}", response_model=FamilyResponse)
async def get_family(
    family_id: UUID,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if payload.get("family_id") != str(family_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another family")

    result = await db.execute(select(FamilyModel).where(FamilyModel.id == family_id))
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    return family


@router.patch("/{family_id}", response_model=FamilyResponse)
async def update_family(
    family_id: UUID,
    request: FamilyUpdate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if payload.get("family_id") != str(family_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another family")

    result = await db.execute(select(FamilyModel).where(FamilyModel.id == family_id))
    family = result.scalar_one_or_none()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(family, field, value)
    family.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(family)
    return family
