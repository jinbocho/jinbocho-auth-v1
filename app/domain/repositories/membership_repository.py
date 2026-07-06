from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import LibraryMembership, MembershipStatus


class MembershipRepository(ABC):
    @abstractmethod
    async def save(self, membership: LibraryMembership) -> LibraryMembership: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> LibraryMembership | None: ...

    @abstractmethod
    async def find_by_user_and_library(self, user_id: UUID, library_id: UUID) -> LibraryMembership | None: ...

    @abstractmethod
    async def find_by_user(
        self, user_id: UUID, statuses: list[MembershipStatus] | None = None
    ) -> list[LibraryMembership]: ...

    @abstractmethod
    async def find_by_library(
        self, library_id: UUID, statuses: list[MembershipStatus] | None = None
    ) -> list[LibraryMembership]: ...

    @abstractmethod
    async def delete(self, id: UUID) -> None: ...
