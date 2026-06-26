import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.enums import UserRole
from app.domain.exceptions import EntityNotFoundError, LastAdminError
from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class DeleteUserInput:
    user_id: UUID
    requester_family_id: UUID


class DeleteUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: DeleteUserInput) -> None:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or user.family_id != input.requester_family_id:
            raise EntityNotFoundError("User not found")

        if user.role == UserRole.ADMIN and user.is_active:
            family = await self._user_repo.find_by_family(user.family_id)
            other_active_admins = any(
                u.id != user.id and u.role == UserRole.ADMIN and u.is_active for u in family
            )
            if not other_active_admins:
                raise LastAdminError("Cannot remove the family's last active admin")

        await self._user_repo.delete(input.user_id)
        logger.info("User %s deleted from family %s", input.user_id, input.requester_family_id)
