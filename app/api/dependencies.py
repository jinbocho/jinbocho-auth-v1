from collections.abc import Callable
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import TokenService
from app.config import settings
from app.domain.repositories import (
    FamilyRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.domain.services import PasswordHasher
from app.infrastructure.database.session import get_db
from app.infrastructure.email import EmailSender
from app.infrastructure.repositories import (
    SQLAlchemyFamilyRepository,
    SQLAlchemyPasswordResetTokenRepository,
    SQLAlchemyRefreshTokenRepository,
    SQLAlchemyUserRepository,
)
from app.infrastructure.security import BcryptPasswordHasher

security = HTTPBearer()
_password_hasher = BcryptPasswordHasher()

_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return SQLAlchemyUserRepository(db)


def get_family_repository(db: AsyncSession = Depends(get_db)) -> FamilyRepository:
    return SQLAlchemyFamilyRepository(db)


def get_password_reset_token_repository(
    db: AsyncSession = Depends(get_db),
) -> PasswordResetTokenRepository:
    return SQLAlchemyPasswordResetTokenRepository(db)


def get_refresh_token_repository(db: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
    return SQLAlchemyRefreshTokenRepository(db)


def get_token_service() -> TokenService:
    return TokenService(settings)


def get_password_hasher() -> PasswordHasher:
    return _password_hasher


def get_email_sender() -> EmailSender:
    return EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.email_from,
        timeout_seconds=settings.smtp_timeout_seconds,
    )


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        raise _AUTH_ERROR

    user_id = payload.get("sub")
    if not user_id:
        raise _AUTH_ERROR

    user = await user_repo.find_by_id(UUID(user_id))
    if not user or not user.is_active:
        raise _AUTH_ERROR

    return payload


def require_role(*roles: str) -> Callable[..., Any]:
    async def checker(payload: dict[str, Any] = Depends(get_current_user_payload)) -> dict[str, Any]:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return checker


__all__ = [
    "AsyncSession",
    "get_db",
    "get_current_user_payload",
    "require_role",
    "get_token_service",
    "get_refresh_token_repository",
    "get_user_repository",
    "get_family_repository",
    "get_password_reset_token_repository",
    "get_email_sender",
    "get_password_hasher",
]

