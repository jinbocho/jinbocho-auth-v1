from dataclasses import dataclass
from uuid import UUID

from app.domain.entities import User
from app.domain.repositories import UserRepository


@dataclass
class ListUsersInput:
    family_id: UUID


@dataclass
class ListUsersOutput:
    users: list[User]


class ListUsersUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: ListUsersInput) -> ListUsersOutput:
        users = await self._user_repo.find_by_family(input.family_id)
        return ListUsersOutput(users=users)
