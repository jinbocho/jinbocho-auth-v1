import logging
from dataclasses import dataclass
from datetime import timedelta

from app.application.services import TokenService, resolve_active_context
from app.domain.entities import MembershipStatus, RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from app.domain.repositories import LibraryRepository, MembershipRepository, RefreshTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)

# Constant-time defense against email enumeration via response timing
# (CWE-208, confirmed via pentest: ~200ms for a real email vs ~15ms for an
# unknown one, since bcrypt.verify was skipped entirely on `not user`). This
# is a valid bcrypt hash of an arbitrary, never-used password — verifying
# against it when the user doesn't exist forces the same bcrypt cost as a
# real login attempt, so timing no longer reveals whether the email exists.
_DUMMY_PASSWORD_HASH = "$2b$12$jDfk5mwms7vdZ8qn7nM1qelTaxrE1XrHSDAB8fv6spbboJTDuS7dK"


@dataclass
class LoginInput:
    email: str
    password: str


@dataclass
class LoginOutput:
    access_token: str
    refresh_token: str
    # None when the token is "context-less" (0 or >1 active memberships and no
    # usable last-selected library) — the frontend must call
    # GET /auth/context/libraries and POST /auth/context/select before
    # hitting any catalog/ai-scoped endpoint.
    library_id: str | None
    role: str | None


class LoginUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        refresh_token_repo: RefreshTokenRepository,
        library_repo: LibraryRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
    ):
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._refresh_token_repo = refresh_token_repo
        self._library_repo = library_repo
        self._token_service = token_service
        self._password_hasher = password_hasher

    async def execute(self, input: LoginInput) -> LoginOutput:
        user = await self._user_repo.find_by_email(input.email)
        password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        password_ok = self._password_hasher.verify(input.password, password_hash)
        if not user or not password_ok:
            logger.warning("Failed login attempt for email %s", input.email)
            raise InvalidCredentialsError("Invalid credentials")
        if not user.is_active:
            logger.warning("Login attempt by inactive user %s", user.id)
            raise InactiveUserError("User is inactive")

        active_memberships = await self._membership_repo.find_by_user(user.id, [MembershipStatus.ACTIVE])
        context = resolve_active_context(user.last_selected_library_id, active_memberships)

        library_id: str | None = None
        role: str | None = None
        kids_mode_enabled = False
        if context is not None:
            chosen_library_id, chosen_role = context
            library_id, role = str(chosen_library_id), chosen_role.value
            chosen_membership = next(m for m in active_memberships if m.library_id == chosen_library_id)
            chosen_membership.last_accessed_at = self._token_service.utcnow()
            await self._membership_repo.save(chosen_membership)
            chosen_library = await self._library_repo.find_by_id(chosen_library_id)
            kids_mode_enabled = chosen_library.kids_mode_enabled if chosen_library else False

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, library_id, role, kids_mode_enabled, user.birth_year,
            user.language.value if user.language else None,
        )
        refresh_token = self._token_service.create_refresh_token()

        token_entity = RefreshToken(
            user_id=user.id,
            token_hash=self._token_service.hash_token(refresh_token),
            expires_at=self._token_service.utcnow() + timedelta(days=self._token_service.refresh_token_expire_days),
        )
        await self._refresh_token_repo.save(token_entity)
        logger.info("User %s logged in", user.id)
        return LoginOutput(access_token=access_token, refresh_token=refresh_token, library_id=library_id, role=role)
