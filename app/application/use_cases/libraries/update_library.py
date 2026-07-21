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
    kids_mode_enabled: bool | None = None


@dataclass
class UpdateLibraryOutput:
    id: UUID
    name: str
    description: str | None = None
    kids_mode_enabled: bool = False


class UpdateLibraryUseCase:
    def __init__(self, library_repo: LibraryRepository, kids_module_enabled: bool) -> None:
        self._library_repo = library_repo
        # Kids Mode (child accounts, reading quizzes/journal/discussion) is
        # its own independently-gated optional module — see settings.kids_module_enabled.
        # It no longer requires the "ai" module; auto-generation of quiz/discussion
        # content still separately requires "ai" (enforced in catalog-service).
        self._kids_module_enabled = kids_module_enabled

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
        if input.kids_mode_enabled is not None:
            if input.kids_mode_enabled and not self._kids_module_enabled:
                raise ForbiddenError("Kids mode is not enabled for this installation")
            library.kids_mode_enabled = input.kids_mode_enabled

        updated_library = await self._library_repo.save(library)
        return UpdateLibraryOutput(
            id=updated_library.id,
            name=updated_library.name,
            description=updated_library.description,
            kids_mode_enabled=updated_library.kids_mode_enabled,
        )
