from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import FamilyRepository


@dataclass
class UpdateFamilyInput:
    family_id: UUID
    requester_family_id: UUID
    name: str | None = None
    description: str | None = None


@dataclass
class UpdateFamilyOutput:
    id: UUID
    name: str
    description: str | None = None


class UpdateFamilyUseCase:
    def __init__(self, family_repo: FamilyRepository) -> None:
        self._family_repo = family_repo

    async def execute(self, input: UpdateFamilyInput) -> UpdateFamilyOutput:
        if input.family_id != input.requester_family_id:
            raise ForbiddenError("Cannot update another family")

        family = await self._family_repo.find_by_id(input.family_id)
        if not family:
            raise EntityNotFoundError("Family not found")

        if input.name is not None:
            family.name = input.name
        if input.description is not None:
            family.description = input.description

        updated_family = await self._family_repo.save(family)
        return UpdateFamilyOutput(
            id=updated_family.id, name=updated_family.name, description=updated_family.description
        )
