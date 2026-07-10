import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.enums import Language, MembershipStatus, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import MembershipRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class GetUserInput:
    user_id: UUID
    requester_library_id: UUID


@dataclass
class GetUserOutput:
    id: UUID
    library_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    annual_reading_goal: int | None = None
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None
    avatar_url: str | None = None
    password_set_at: datetime | None = None
    tour_completed_at: datetime | None = None


class GetUserUseCase:
    """Fetches a user's profile within one library's context. Authorization
    is membership-based (does this user have an active membership in
    requester_library_id?) rather than the legacy users.library_id scalar —
    that scalar only ever reflects a user's *original* library, so it breaks
    for anyone reachable in a second library only through a membership row
    (e.g. a plain GET /users/me right after switching into it)."""

    def __init__(self, user_repo: UserRepository, membership_repo: MembershipRepository):
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, input: GetUserInput) -> GetUserOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user:
            raise EntityNotFoundError("User not found")
        membership = await self._membership_repo.find_by_user_and_library(user.id, input.requester_library_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise EntityNotFoundError("User not found")

        logger.debug("User %s fetched by library %s", input.user_id, input.requester_library_id)
        return GetUserOutput(
            id=user.id,
            library_id=input.requester_library_id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            is_active=user.is_active,
            annual_reading_goal=user.annual_reading_goal,
            language=user.language,
            theme_name=user.theme_name,
            theme_mode=user.theme_mode,
            avatar_url=user.avatar_url,
            password_set_at=user.password_set_at,
            tour_completed_at=user.tour_completed_at,
        )
