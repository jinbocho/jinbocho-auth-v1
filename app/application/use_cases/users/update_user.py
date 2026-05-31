from dataclasses import dataclass
from uuid import UUID

from app.domain.repositories import UserRepository


@dataclass
class UpdateUserInput:
    user_id: UUID
    requester_family_id: UUID
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


@dataclass
class UpdateUserOutput:
    id: UUID
    family_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class UpdateUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: UpdateUserInput) -> UpdateUserOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or user.family_id != input.requester_family_id:
            raise LookupError("User not found")

        if input.full_name is not None:
            user.full_name = input.full_name
        if input.role is not None:
            user.role = input.role
        if input.is_active is not None:
            user.is_active = input.is_active

        updated_user = await self._user_repo.save(user)
        return UpdateUserOutput(
            id=updated_user.id,
            family_id=updated_user.family_id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=updated_user.role,
            is_active=updated_user.is_active,
        )
