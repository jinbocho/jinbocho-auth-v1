import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class DeleteAvatarInput:
    user_id: UUID
    family_id: UUID


class DeleteAvatarUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, inp: DeleteAvatarInput) -> None:
        user = await self._user_repo.find_by_id(inp.user_id)
        if not user or user.family_id != inp.family_id:
            raise LookupError("User not found")

        user.avatar_url = None
        await self._user_repo.save(user)
        logger.info("Avatar deleted for user %s", inp.user_id)
