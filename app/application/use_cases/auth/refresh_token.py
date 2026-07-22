import logging
from dataclasses import dataclass
from datetime import timedelta

from app.application.services import TokenService, resolve_active_context
from app.domain.entities import MembershipStatus, RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from app.domain.repositories import LibraryRepository, MembershipRepository, RefreshTokenRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class RefreshTokenInput:
    refresh_token: str


@dataclass
class RefreshTokenOutput:
    access_token: str
    refresh_token: str
    library_id: str | None
    role: str | None


class RefreshTokenUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        refresh_token_repo: RefreshTokenRepository,
        library_repo: LibraryRepository,
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._refresh_token_repo = refresh_token_repo
        self._library_repo = library_repo
        self._token_service = token_service

    async def execute(self, input: RefreshTokenInput) -> RefreshTokenOutput:
        now = self._token_service.utcnow()
        token_hash = self._token_service.hash_token(input.refresh_token)
        stored_token = await self._refresh_token_repo.find_by_hash(token_hash)

        if not stored_token:
            raise InvalidCredentialsError("Invalid refresh token")
        if stored_token.expires_at < now:
            raise InvalidCredentialsError("Token expired")

        # Atomic claim (single conditional UPDATE, see
        # RefreshTokenRepository.revoke): concurrent requests replaying the
        # same stolen/leaked token race here, and exactly one can win —
        # confirmed via pentest that a plain "read revoked_at, then revoke"
        # sequence let 5 concurrent requests all pass validation and all
        # mint a new token pair from a single refresh token.
        claimed = await self._refresh_token_repo.revoke(token_hash)
        if not claimed:
            raise InvalidCredentialsError("Token revoked")

        user = await self._user_repo.find_by_id(stored_token.user_id)
        if not user:
            raise InvalidCredentialsError("Invalid refresh token")
        if not user.is_active:
            raise InactiveUserError("User is inactive")

        # Re-resolve on every refresh, not just at login: a membership
        # suspended/revoked while the access token was still live must not
        # survive past the next refresh — this is the enforcement point that
        # bounds the exposure window described in the plan's authz section.
        active_memberships = await self._membership_repo.find_by_user(user.id, [MembershipStatus.ACTIVE])
        context = resolve_active_context(user.last_selected_library_id, active_memberships)

        library_id: str | None = None
        role: str | None = None
        kids_mode_enabled = False
        if context is not None:
            chosen_library_id, chosen_role = context
            library_id, role = str(chosen_library_id), chosen_role.value
            chosen_membership = next(m for m in active_memberships if m.library_id == chosen_library_id)
            chosen_membership.last_accessed_at = now
            await self._membership_repo.save(chosen_membership)
            chosen_library = await self._library_repo.find_by_id(chosen_library_id)
            kids_mode_enabled = chosen_library.kids_mode_enabled if chosen_library else False

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, library_id, role, kids_mode_enabled, user.birth_year,
            user.language.value if user.language else None,
        )
        new_refresh_token = self._token_service.create_refresh_token()

        new_token_entity = RefreshToken(
            user_id=user.id,
            token_hash=self._token_service.hash_token(new_refresh_token),
            expires_at=now + timedelta(days=self._token_service.refresh_token_expire_days),
        )
        await self._refresh_token_repo.save(new_token_entity)
        logger.debug("Refresh token rotated for user %s", user.id)
        return RefreshTokenOutput(
            access_token=access_token, refresh_token=new_refresh_token, library_id=library_id, role=role
        )
