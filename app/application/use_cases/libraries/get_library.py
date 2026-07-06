from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import LibraryRepository


@dataclass
class GetLibraryInput:
    library_id: UUID
    requester_library_id: UUID


@dataclass
class GetLibraryOutput:
    id: UUID
    name: str
    description: str | None = None


class GetLibraryUseCase:
    def __init__(self, library_repo: LibraryRepository) -> None:
        self._library_repo = library_repo

    async def execute(self, input: GetLibraryInput) -> GetLibraryOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot access another library")

        library = await self._library_repo.find_by_id(input.library_id)
        if not library:
            raise EntityNotFoundError("Library not found")

        return GetLibraryOutput(id=library.id, name=library.name, description=library.description)
