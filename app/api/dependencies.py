from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import TokenService
from app.config import settings
from app.domain.repositories import RefreshTokenRepository
from app.infrastructure.database.session import get_db
from app.infrastructure.models import UserModel
from app.infrastructure.repositories import SQLAlchemyRefreshTokenRepository

security = HTTPBearer()

_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise _AUTH_ERROR

    user_id = payload.get("sub")
    if not user_id:
        raise _AUTH_ERROR

    user = await db.get(UserModel, UUID(user_id))
    if not user or not user.is_active:
        raise _AUTH_ERROR

    return payload


def require_role(*roles: str):
    async def checker(payload: dict = Depends(get_current_user_payload)):
        if payload.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return checker


def get_token_service() -> TokenService:
    return TokenService(settings)


def get_refresh_token_repository(db: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
    return SQLAlchemyRefreshTokenRepository(db)


__all__ = [
    "AsyncSession",
    "get_db",
    "get_current_user_payload",
    "require_role",
    "get_token_service",
    "get_refresh_token_repository",
]

