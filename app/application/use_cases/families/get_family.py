from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import FamilyRepository


@dataclass
class GetFamilyInput:
    family_id: UUID
    requester_family_id: UUID


@dataclass
class GetFamilyOutput:
    id: UUID
    name: str
    description: str | None = None


class GetFamilyUseCase:
    def __init__(self, family_repo: FamilyRepository) -> None:
        self._family_repo = family_repo

    async def execute(self, input: GetFamilyInput) -> GetFamilyOutput:
        if input.family_id != input.requester_family_id:
            raise ForbiddenError("Cannot access another family")

        family = await self._family_repo.find_by_id(input.family_id)
        if not family:
            raise EntityNotFoundError("Family not found")

        return GetFamilyOutput(id=family.id, name=family.name, description=family.description)
