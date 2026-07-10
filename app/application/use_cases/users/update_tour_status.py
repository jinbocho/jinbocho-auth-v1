import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities.enums import MembershipStatus
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import MembershipRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class UpdateTourStatusInput:
    user_id: UUID
    requester_library_id: UUID
    completed: bool


class UpdateTourStatusUseCase:
    """Powers POST /users/me/tour/complete and /tour/reset. The timestamp is
    always server-set (see User.tour_completed_at) — callers only say whether
    the tour is done or not, never supply a moment in time."""

    def __init__(self, user_repo: UserRepository, membership_repo: MembershipRepository):
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, input: UpdateTourStatusInput) -> None:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user:
            raise EntityNotFoundError("User not found")
        membership = await self._membership_repo.find_by_user_and_library(user.id, input.requester_library_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise EntityNotFoundError("User not found")

        user.tour_completed_at = datetime.now(timezone.utc) if input.completed else None
        await self._user_repo.save(user)
        logger.info("User %s tour status set to completed=%s", input.user_id, input.completed)
