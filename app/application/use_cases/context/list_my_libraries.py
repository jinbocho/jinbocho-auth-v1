from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.repositories import LibraryRepository, MembershipRepository


@dataclass
class ListMyLibrariesInput:
    user_id: UUID


@dataclass
class LibrarySummary:
    library_id: UUID
    name: str
    role: UserRole
    status: MembershipStatus
    last_accessed_at: datetime | None


@dataclass
class ListMyLibrariesOutput:
    libraries: list[LibrarySummary]


class ListMyLibrariesUseCase:
    """Powers the post-login library picker and the header switcher. Deliberately
    includes `invited` memberships (shown as pending invites) and `suspended`
    ones (so the user understands why a library disappeared from their
    selectable set) but not `revoked` — those are gone for good."""

    def __init__(self, membership_repo: MembershipRepository, library_repo: LibraryRepository):
        self._membership_repo = membership_repo
        self._library_repo = library_repo

    async def execute(self, input: ListMyLibrariesInput) -> ListMyLibrariesOutput:
        memberships = await self._membership_repo.find_by_user(
            input.user_id, [MembershipStatus.ACTIVE, MembershipStatus.INVITED, MembershipStatus.SUSPENDED]
        )
        libraries = []
        for m in memberships:
            library = await self._library_repo.find_by_id(m.library_id)
            if library is None:
                continue
            libraries.append(
                LibrarySummary(
                    library_id=m.library_id,
                    name=library.name,
                    role=m.role,
                    status=m.status,
                    last_accessed_at=m.last_accessed_at,
                )
            )
        libraries.sort(key=lambda lib: lib.last_accessed_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return ListMyLibrariesOutput(libraries=libraries)
