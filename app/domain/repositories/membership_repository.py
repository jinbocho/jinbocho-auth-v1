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
    async def lock_active_admins(self, library_id: UUID) -> list[LibraryMembership]:
        """Like find_by_library(library_id, [ACTIVE]) but takes a row lock
        (SELECT ... FOR UPDATE) on the returned rows. Used only for the
        "don't demote/remove/suspend the last active admin" check: without
        the lock, two concurrent requests both demoting a different one of
        the library's exactly-two admins each read "the other is still an
        active admin" before either write lands, and both succeed — leaving
        the library with zero admins (confirmed via pentest). The lock
        forces the second request to wait until the first commits, so it
        re-reads the post-demotion state and correctly rejects."""
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> None: ...
