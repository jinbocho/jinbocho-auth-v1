from collections.abc import Callable
from typing import NotRequired, TypedDict, cast
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
    RegisterLibraryUseCase,
    RequestPasswordResetUseCase,
    ResetPasswordUseCase,
)
from app.application.use_cases.children import CreateChildAccountUseCase
from app.application.use_cases.context import ListMyLibrariesUseCase, SelectLibraryContextUseCase
from app.application.use_cases.libraries import (
    ConfirmLibraryDeletionUseCase,
    DeleteLibraryUseCase,
    GetLibraryUseCase,
    RevokeLibrarySessionsUseCase,
    UpdateLibraryUseCase,
)
from app.application.use_cases.memberships import (
    AcceptInvitationUseCase,
    DeclineInvitationUseCase,
    GetMemberUseCase,
    InviteMemberUseCase,
    ListMembersUseCase,
    ListMembershipActivityUseCase,
    RemoveMembershipUseCase,
    SearchMembersUseCase,
    UpdateMembershipUseCase,
)
from app.application.use_cases.users import (
    ConfirmEmailChangeUseCase,
    CreateUserUseCase,
    DeleteAvatarUseCase,
    ExportLibraryDataUseCase,
    GetUserUseCase,
    ImportUsersUseCase,
    ListUsersUseCase,
    RequestEmailChangeUseCase,
    ResendInviteUseCase,
    SearchUsersUseCase,
    UpdateUserUseCase,
    UpdateTourStatusUseCase,
    DeleteUserUseCase,
    UploadAvatarUseCase,
)
from app.config import settings
from app.domain.repositories import (
    EmailChangeTokenRepository,
    LibraryRepository,
    MembershipRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.domain.services import PasswordHasher
from app.infrastructure.database.session import get_db
from app.infrastructure.email import EmailSender
from app.infrastructure.repositories import (
    SQLAlchemyEmailChangeTokenRepository,
    SQLAlchemyLibraryRepository,
    SQLAlchemyMembershipRepository,
    SQLAlchemyPasswordResetTokenRepository,
    SQLAlchemyRefreshTokenRepository,
    SQLAlchemyUserRepository,
)
from app.infrastructure.security import BcryptPasswordHasher


class JWTPayload(TypedDict):
    sub: str
    email: str
    # Absent on a "context-less" token — one issued when the user hasn't
    # selected an active library yet (0 or >1 memberships at login/refresh).
    library_id: NotRequired[str]
    role: NotRequired[str]
    # Mirrors the target library's Library.kids_mode_enabled at issuance —
    # absent on context-less tokens, same as library_id/role.
    kids_mode_enabled: NotRequired[bool]
    iss: str
    aud: str
    iat: int
    exp: int


# auto_error=False: fastapi>=0.116/starlette>=1.0 changed HTTPBearer's own
# missing-credentials response from 403 to 401 (see get_current_user_payload
# below) — the app's established contract, tested and relied on by the FE's
# 401-triggers-refresh logic, is 403 for "no credentials at all" vs 401 for
# "credentials present but invalid/expired". Handling it explicitly here
# keeps that contract stable regardless of what the library defaults to.
security = HTTPBearer(auto_error=False)
_password_hasher = BcryptPasswordHasher()
_token_service = TokenService(settings)

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


def get_library_repository(db: AsyncSession = Depends(get_db)) -> LibraryRepository:
    return SQLAlchemyLibraryRepository(db)


def get_membership_repository(db: AsyncSession = Depends(get_db)) -> MembershipRepository:
    return SQLAlchemyMembershipRepository(db)


def get_password_reset_token_repository(
    db: AsyncSession = Depends(get_db),
) -> PasswordResetTokenRepository:
    return SQLAlchemyPasswordResetTokenRepository(db)


def get_email_change_token_repository(
    db: AsyncSession = Depends(get_db),
) -> EmailChangeTokenRepository:
    return SQLAlchemyEmailChangeTokenRepository(db)


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
    # Built fresh per call (not a module-level singleton) so it always reads
    # the current settings.smtp_host — tests monkeypatch that value to force
    # the console fallback, which a frozen-at-import singleton would ignore.
    return EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.email_from,
        timeout_seconds=settings.smtp_timeout_seconds,
    )


# ---------------------------------------------------------------------------
# Auth / JWT helpers
# ---------------------------------------------------------------------------

async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository),
) -> JWTPayload:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
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


async def require_library_context(payload: JWTPayload = Depends(get_current_user_payload)) -> JWTPayload:
    """Gate for every endpoint scoped to `payload["library_id"]` — rejects a
    context-less token (see JWTPayload) with a clean 403 instead of letting
    endpoints KeyError on a missing claim. A context-less token may only call
    /auth/context/* (to pick a library) and /auth/logout."""
    if "library_id" not in payload:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active library selected")
    return payload


def require_role(*roles: str) -> Callable[..., object]:
    async def checker(payload: JWTPayload = Depends(require_library_context)) -> JWTPayload:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return checker


# Kids-mode role gates. "child" never appears in any require_role(...)
# allowlist elsewhere in the codebase, so every pre-existing endpoint already
# default-denies a child token — these two only *open* the dedicated
# kids-mode surface (child self-service vs. parent-only management).
require_child = require_role("child")
require_parent = require_role("admin", "editor")


# ---------------------------------------------------------------------------
# Use case factories — complex endpoints wire repos/services here, not inline
# ---------------------------------------------------------------------------

def get_register_library_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    email_sender: EmailService = Depends(get_email_sender),
) -> RegisterLibraryUseCase:
    return RegisterLibraryUseCase(
        library_repo, user_repo, membership_repo, password_hasher, email_sender, settings.frontend_base_url
    )


def get_login_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> LoginUseCase:
    return LoginUseCase(
        user_repo, membership_repo, refresh_token_repo, library_repo, token_service, password_hasher
    )


def get_refresh_token_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
    token_service: TokenService = Depends(get_token_service),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(user_repo, membership_repo, refresh_token_repo, library_repo, token_service)


def get_list_my_libraries_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
) -> ListMyLibrariesUseCase:
    return ListMyLibrariesUseCase(membership_repo, library_repo)


def get_select_library_context_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
    token_service: TokenService = Depends(get_token_service),
) -> SelectLibraryContextUseCase:
    return SelectLibraryContextUseCase(user_repo, membership_repo, library_repo, token_service)


def get_accept_invitation_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> AcceptInvitationUseCase:
    return AcceptInvitationUseCase(membership_repo)


def get_decline_invitation_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> DeclineInvitationUseCase:
    return DeclineInvitationUseCase(membership_repo)


def get_invite_member_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> InviteMemberUseCase:
    return InviteMemberUseCase(
        user_repo, membership_repo, library_repo, reset_token_repo, email_sender, token_service, password_hasher,
        settings.invite_expire_minutes, settings.frontend_base_url,
    )


def get_create_child_account_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    library_repo: LibraryRepository = Depends(get_library_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> CreateChildAccountUseCase:
    return CreateChildAccountUseCase(user_repo, membership_repo, library_repo, password_hasher)


def get_list_members_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> ListMembersUseCase:
    return ListMembersUseCase(membership_repo, user_repo)


def get_get_member_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> GetMemberUseCase:
    return GetMemberUseCase(membership_repo, user_repo)


def get_list_membership_activity_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> ListMembershipActivityUseCase:
    return ListMembershipActivityUseCase(membership_repo, user_repo)


def get_search_members_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> SearchMembersUseCase:
    return SearchMembersUseCase(membership_repo, user_repo)


def get_search_users_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> SearchUsersUseCase:
    return SearchUsersUseCase(user_repo)


def get_update_membership_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UpdateMembershipUseCase:
    return UpdateMembershipUseCase(membership_repo)


def get_remove_membership_use_case(
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> RemoveMembershipUseCase:
    return RemoveMembershipUseCase(membership_repo)


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
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repo, membership_repo, reset_token_repo, email_sender, token_service, password_hasher,
        settings.invite_expire_minutes, settings.frontend_base_url,
    )


def get_resend_invite_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
) -> ResendInviteUseCase:
    return ResendInviteUseCase(
        user_repo, membership_repo, reset_token_repo, email_sender, token_service,
        settings.invite_expire_minutes, settings.frontend_base_url,
    )


def get_update_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UpdateUserUseCase:
    return UpdateUserUseCase(user_repo, membership_repo)


def get_get_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> GetUserUseCase:
    return GetUserUseCase(user_repo, membership_repo)


def get_list_users_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> ListUsersUseCase:
    return ListUsersUseCase(user_repo, membership_repo)


def get_export_library_data_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> ExportLibraryDataUseCase:
    return ExportLibraryDataUseCase(library_repo, user_repo)


def get_update_tour_status_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UpdateTourStatusUseCase:
    return UpdateTourStatusUseCase(user_repo, membership_repo)


def get_request_email_change_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    email_change_token_repo: EmailChangeTokenRepository = Depends(get_email_change_token_repository),
    email_sender: EmailService = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
) -> RequestEmailChangeUseCase:
    return RequestEmailChangeUseCase(
        user_repo, email_change_token_repo, email_sender, token_service,
        settings.email_change_expire_minutes, settings.frontend_base_url,
    )


def get_confirm_email_change_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    email_change_token_repo: EmailChangeTokenRepository = Depends(get_email_change_token_repository),
    token_service: TokenService = Depends(get_token_service),
) -> ConfirmEmailChangeUseCase:
    return ConfirmEmailChangeUseCase(user_repo, email_change_token_repo, token_service)


def get_delete_user_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
) -> DeleteUserUseCase:
    return DeleteUserUseCase(user_repo)


def get_upload_avatar_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UploadAvatarUseCase:
    return UploadAvatarUseCase(user_repo, membership_repo)


def get_delete_avatar_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> DeleteAvatarUseCase:
    return DeleteAvatarUseCase(user_repo, membership_repo)


def get_get_library_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
) -> GetLibraryUseCase:
    return GetLibraryUseCase(library_repo)


def get_update_library_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
) -> UpdateLibraryUseCase:
    return UpdateLibraryUseCase(library_repo, settings.kids_module_enabled)


def get_confirm_library_deletion_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> ConfirmLibraryDeletionUseCase:
    return ConfirmLibraryDeletionUseCase(library_repo, user_repo, password_hasher)


def get_delete_library_use_case(
    library_repo: LibraryRepository = Depends(get_library_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> DeleteLibraryUseCase:
    return DeleteLibraryUseCase(library_repo, user_repo, password_hasher)


def get_revoke_library_sessions_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> RevokeLibrarySessionsUseCase:
    return RevokeLibrarySessionsUseCase(user_repo, refresh_token_repo)


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
    "require_library_context",
    "verify_internal_token",
    "require_role",
    "require_child",
    "require_parent",
    "get_token_service",
    "get_refresh_token_repository",
    "get_user_repository",
    "get_library_repository",
    "get_membership_repository",
    "get_password_reset_token_repository",
    "get_email_change_token_repository",
    "get_email_sender",
    "get_password_hasher",
    "get_register_library_use_case",
    "get_login_use_case",
    "get_refresh_token_use_case",
    "get_logout_use_case",
    "get_forgot_password_use_case",
    "get_reset_password_use_case",
    "get_create_user_use_case",
    "get_update_user_use_case",
    "get_get_user_use_case",
    "get_list_users_use_case",
    "get_export_library_data_use_case",
    "get_update_tour_status_use_case",
    "get_request_email_change_use_case",
    "get_confirm_email_change_use_case",
    "get_delete_user_use_case",
    "get_upload_avatar_use_case",
    "get_delete_avatar_use_case",
    "get_resend_invite_use_case",
    "get_import_users_use_case",
    "get_get_library_use_case",
    "get_update_library_use_case",
    "get_confirm_library_deletion_use_case",
    "get_delete_library_use_case",
    "get_revoke_library_sessions_use_case",
    "get_list_my_libraries_use_case",
    "get_select_library_context_use_case",
    "get_accept_invitation_use_case",
    "get_decline_invitation_use_case",
    "get_get_member_use_case",
    "get_invite_member_use_case",
    "get_create_child_account_use_case",
    "get_list_members_use_case",
    "get_list_membership_activity_use_case",
    "get_search_members_use_case",
    "get_search_users_use_case",
    "get_update_membership_use_case",
    "get_remove_membership_use_case",
]
