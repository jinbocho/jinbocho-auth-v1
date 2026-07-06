from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Library


class LibraryRepository(ABC):
    @abstractmethod
    async def save(self, library: Library) -> Library: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> Library | None: ...

    @abstractmethod
    async def delete(self, id: UUID) -> None:
        """Deletes the library — the DB cascades to every user (and from
        there, every refresh/password-reset token). Used by the account
        deletion flow, after the caller's own confirmation/password check."""
        ...
