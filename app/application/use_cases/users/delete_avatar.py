import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.enums import MembershipStatus
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import MembershipRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class DeleteAvatarInput:
    user_id: UUID
    library_id: UUID


class DeleteAvatarUseCase:
    def __init__(self, user_repo: UserRepository, membership_repo: MembershipRepository) -> None:
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, inp: DeleteAvatarInput) -> None:
        user = await self._user_repo.find_by_id(inp.user_id)
        if not user:
            raise EntityNotFoundError("User not found")
        membership = await self._membership_repo.find_by_user_and_library(user.id, inp.library_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise EntityNotFoundError("User not found")

        user.avatar_url = None
        await self._user_repo.save(user)
        logger.info("Avatar deleted for user %s", inp.user_id)
