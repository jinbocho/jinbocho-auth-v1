from dataclasses import dataclass
from uuid import UUID

from app.domain.repositories import UserRepository


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
            raise LookupError("User not found")
        await self._user_repo.delete(input.user_id)
