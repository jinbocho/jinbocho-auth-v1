from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_payload, get_db, require_role
from app.application.use_cases import pwd_context
from app.infrastructure.models import UserModel

router = APIRouter()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(pattern="^(admin|editor|viewer)$")


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


@router.get("/me", response_model=UserResponse)
async def get_me(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(UserModel, UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserModel).where(UserModel.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = UserModel(
        family_id=UUID(payload["family_id"]),
        email=request.email,
        password_hash=pwd_context.hash(request.password),
        full_name=request.full_name,
        role=request.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    family_id = UUID(payload["family_id"])
    result = await db.execute(
        select(UserModel).where(UserModel.family_id == family_id).order_by(UserModel.created_at)
    )
    return result.scalars().all()


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user or str(user.family_id) != payload.get("family_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user or str(user.family_id) != payload.get("family_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.commit()
