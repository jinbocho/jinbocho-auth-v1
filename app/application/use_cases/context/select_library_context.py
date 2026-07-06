import logging
from dataclasses import dataclass
from uuid import UUID

from app.application.services import TokenService
from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import InactiveUserError, NotAMemberError
from app.domain.repositories import MembershipRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class SelectLibraryContextInput:
    user_id: UUID
    library_id: UUID


@dataclass
class SelectLibraryContextOutput:
    access_token: str
    library_id: UUID
    role: UserRole


class SelectLibraryContextUseCase:
    """Mints a new, library-scoped access token after the frontend's library
    picker/switcher posts a choice. This is the sole enforcement point that
    turns "I am this user" into "I am this user, acting in this library" —
    every catalog/ai request downstream trusts the library_id/role claims it
    produces."""

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._token_service = token_service

    async def execute(self, input: SelectLibraryContextInput) -> SelectLibraryContextOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or not user.is_active:
            raise InactiveUserError("User is inactive")

        membership = await self._membership_repo.find_by_user_and_library(input.user_id, input.library_id)
        if not membership or membership.status != MembershipStatus.ACTIVE:
            raise NotAMemberError("Not an active member of this library")

        now = self._token_service.utcnow()
        membership.last_accessed_at = now
        await self._membership_repo.save(membership)

        user.last_selected_library_id = input.library_id
        await self._user_repo.save(user)

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, str(membership.library_id), membership.role.value
        )
        logger.info("User %s selected library %s", user.id, membership.library_id)
        return SelectLibraryContextOutput(access_token=access_token, library_id=membership.library_id, role=membership.role)
