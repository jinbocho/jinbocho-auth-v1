from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from jose import jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.application.use_cases import RegisterFamilyInput, RegisterFamilyUseCase, pwd_context
from app.config import settings
from app.infrastructure.models import RefreshTokenModel, UserModel
from app.infrastructure.repositories import SQLAlchemyFamilyRepository, SQLAlchemyUserRepository

router = APIRouter()


class RegisterRequest(BaseModel):
    family_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    admin_full_name: str = Field(min_length=1, max_length=255)


class RegisterResponse(BaseModel):
    family_id: UUID
    user_id: UUID


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_access_token_payload(user: UserModel) -> dict:
    return {
        "sub": str(user.id),
        "email": user.email,
        "family_id": str(user.family_id),
        "role": user.role,
    }


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    return uuid4().hex


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_family(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user_repo = SQLAlchemyUserRepository(db)
    if await user_repo.find_by_email(request.admin_email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    use_case = RegisterFamilyUseCase(SQLAlchemyFamilyRepository(db), user_repo)
    result = await use_case.execute(
        RegisterFamilyInput(
            family_name=request.family_name,
            admin_email=request.admin_email,
            admin_password=request.admin_password,
            admin_full_name=request.admin_full_name,
        )
    )
    await db.commit()
    return RegisterResponse(family_id=result.family_id, user_id=result.user_id)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.email == request.email))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    access_token = create_access_token(build_access_token_payload(user))
    refresh_token = create_refresh_token()
    db.add(
        RefreshTokenModel(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    now = utcnow()
    result = await db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == hash_token(request.refresh_token))
    )
    stored_token = result.scalar_one_or_none()
    if not stored_token or stored_token.expires_at < now or stored_token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await db.get(UserModel, stored_token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    stored_token.revoked_at = now
    new_refresh_token = create_refresh_token()
    db.add(
        RefreshTokenModel(
            user_id=user.id,
            token_hash=hash_token(new_refresh_token),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(build_access_token_payload(user)),
        refresh_token=new_refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: LogoutRequest, db: AsyncSession = Depends(get_db)) -> Response:
    result = await db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == hash_token(request.refresh_token))
    )
    stored_token = result.scalar_one_or_none()
    if stored_token and stored_token.revoked_at is None:
        stored_token.revoked_at = utcnow()
        await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
