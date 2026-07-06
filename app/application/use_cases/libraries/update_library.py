from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import LibraryRepository


@dataclass
class UpdateLibraryInput:
    library_id: UUID
    requester_library_id: UUID
    name: str | None = None
    description: str | None = None


@dataclass
class UpdateLibraryOutput:
    id: UUID
    name: str
    description: str | None = None


class UpdateLibraryUseCase:
    def __init__(self, library_repo: LibraryRepository) -> None:
        self._library_repo = library_repo

    async def execute(self, input: UpdateLibraryInput) -> UpdateLibraryOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot update another library")

        library = await self._library_repo.find_by_id(input.library_id)
        if not library:
            raise EntityNotFoundError("Library not found")

        if input.name is not None:
            library.name = input.name
        if input.description is not None:
            library.description = input.description

        updated_library = await self._library_repo.save(library)
        return UpdateLibraryOutput(
            id=updated_library.id, name=updated_library.name, description=updated_library.description
        )
