from dataclasses import dataclass
from uuid import UUID

from app.domain.repositories import UserRepository


@dataclass
class ListUsersInput:
    family_id: UUID


@dataclass
class ListUsersOutput:
    users: list[dict]


class ListUsersUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: ListUsersInput) -> ListUsersOutput:
        # Note: UserRepository doesn't have list_by_family yet, would need to add it
        # For now, returning empty list as placeholder
        return ListUsersOutput(users=[])
