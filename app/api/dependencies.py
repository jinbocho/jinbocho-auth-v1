from collections.abc import Callable
from typing import TypedDict, cast
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import EmailService
from app.application.services import TokenService
from app.application.use_cases.auth import (
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
    RegisterFamilyUseCase,
    RequestPasswordResetUseCase,
    ResetPasswordUseCase,
)
from app.application.use_cases.families import (
    ConfirmFamilyDeletionUseCase,
    DeleteFamilyUseCase,
    GetFamilyUseCase,
    RevokeFamilySessionsUseCase,
    UpdateFamilyUseCase,
)
from app.application.use_cases.users import (
    CreateUserUseCase,
    DeleteAvatarUseCase,
    ImportUsersUseCase,
    ResendInviteUseCase,
    UpdateUserUseCase,
    DeleteUserUseCase,
    UploadAvatarUseCase,
)
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


class JWTPayload(TypedDict):
    sub: str
    email: str
    family_id: str
    role: str
    iss: str
    aud: str
    iat: int
    exp: int


security = HTTPBearer()
_password_hasher = BcryptPasswordHasher()
_token_service = TokenService(settings)
_email_sender = EmailSender(
    host=settings.smtp_host,
    port=settings.smtp_port,
    user=settings.smtp_user,
    password=settings.smtp_password,
    from_address=settings.email_from,
    timeout_seconds=settings.smtp_timeout_seconds,
)

_AUTH_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid token",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Repository providers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Service providers (module-level singletons — stateless)
# ---------------------------------------------------------------------------

def get_token_service() -> TokenService:
    return _token_service


def get_password_hasher() -> PasswordHasher:
    return _password_hasher


def get_email_sender() -> EmailService:
    return _email_sender


# ---------------------------------------------------------------------------
# Auth / JWT helpers
# ---------------------------------------------------------------------------

async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository),
) -> JWTPayload:
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

    return cast(JWTPayload, payload)


async def verify_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Gate for service-to-service endpoints — caller must present the shared secret."""
    if not settings.internal_service_token or x_internal_token != settings.internal_service_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")


def require_role(*roles: str) -> Callable[..., object]:
    async def checker(payload: JWTPayload = Depends(get_current_user_payload)) -> JWTPayload:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return checker


# ---------------------------------------------------------------------------
# Use case factories — complex endpoints wire repos/services here, not inline
# ---------------------------------------------------------------------------

def get_register_family_use_case(
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    email_sender: EmailService = Depends(get_email_sender),
) -> RegisterFamilyUseCase:
    return RegisterFamilyUseCase(family_repo, user_repo, password_hasher, email_sender, settings.frontend_base_url)


def get_login_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> LoginUseCase:
    return LoginUseCase(user_repo, refresh_token_repo, token_service, password_hasher)


def get_refresh_token_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    token_service: TokenService = Depends(get_token_service),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(user_repo, refresh_token_repo, token_service)


def get_logout_use_case(
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    token_service: TokenService = Depends(get_token_service),
) -> LogoutUseCase:
    return LogoutUseCase(refresh_token_repo, token_service)


def get_forgot_password_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        user_repo, reset_token_repo, email_sender, token_service,
        settings.password_reset_expire_minutes, settings.frontend_base_url,
    )


def get_reset_password_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> ResetPasswordUseCase:
    return ResetPasswordUseCase(user_repo, reset_token_repo, token_service, password_hasher)


def get_create_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repo, reset_token_repo, email_sender, token_service, password_hasher,
        settings.invite_expire_minutes, settings.frontend_base_url,
    )


def get_resend_invite_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
) -> ResendInviteUseCase:
    return ResendInviteUseCase(
        user_repo, reset_token_repo, email_sender, token_service,
        settings.invite_expire_minutes, settings.frontend_base_url,
    )


def get_update_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UpdateUserUseCase:
    return UpdateUserUseCase(user_repo)


def get_delete_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> DeleteUserUseCase:
    return DeleteUserUseCase(user_repo)


def get_upload_avatar_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UploadAvatarUseCase:
    return UploadAvatarUseCase(user_repo)


def get_delete_avatar_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> DeleteAvatarUseCase:
    return DeleteAvatarUseCase(user_repo)


def get_get_family_use_case(
    family_repo: FamilyRepository = Depends(get_family_repository),
) -> GetFamilyUseCase:
    return GetFamilyUseCase(family_repo)


def get_update_family_use_case(
    family_repo: FamilyRepository = Depends(get_family_repository),
) -> UpdateFamilyUseCase:
    return UpdateFamilyUseCase(family_repo)


def get_confirm_family_deletion_use_case(
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> ConfirmFamilyDeletionUseCase:
    return ConfirmFamilyDeletionUseCase(family_repo, user_repo, password_hasher)


def get_delete_family_use_case(
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> DeleteFamilyUseCase:
    return DeleteFamilyUseCase(family_repo, user_repo, password_hasher)


def get_revoke_family_sessions_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> RevokeFamilySessionsUseCase:
    return RevokeFamilySessionsUseCase(user_repo, refresh_token_repo)


def get_import_users_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    create_user_uc: CreateUserUseCase = Depends(get_create_user_use_case),
    update_user_uc: UpdateUserUseCase = Depends(get_update_user_use_case),
) -> ImportUsersUseCase:
    return ImportUsersUseCase(user_repo, create_user_uc, update_user_uc)


__all__ = [
    "AsyncSession",
    "JWTPayload",
    "get_db",
    "get_current_user_payload",
    "verify_internal_token",
    "require_role",
    "get_token_service",
    "get_refresh_token_repository",
    "get_user_repository",
    "get_family_repository",
    "get_password_reset_token_repository",
    "get_email_sender",
    "get_password_hasher",
    "get_register_family_use_case",
    "get_login_use_case",
    "get_refresh_token_use_case",
    "get_logout_use_case",
    "get_forgot_password_use_case",
    "get_reset_password_use_case",
    "get_create_user_use_case",
    "get_update_user_use_case",
    "get_delete_user_use_case",
    "get_upload_avatar_use_case",
    "get_delete_avatar_use_case",
    "get_resend_invite_use_case",
    "get_import_users_use_case",
    "get_get_family_use_case",
    "get_update_family_use_case",
    "get_confirm_family_deletion_use_case",
    "get_delete_family_use_case",
    "get_revoke_family_sessions_use_case",
]
