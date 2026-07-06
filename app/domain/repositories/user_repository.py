from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> User: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> User | None: ...

    @abstractmethod
    async def find_by_library(self, library_id: UUID) -> list[User]: ...

    @abstractmethod
    async def search_active_excluding_library(
        self, query: str, exclude_library_id: UUID, limit: int
    ) -> list[User]:
        """Cross-tenant typeahead for inviting an existing account into a
        *different* library — the one search in the system that isn't
        scoped to a single library's roster. Excludes anyone already a
        non-revoked member of exclude_library_id (nothing to invite there)."""
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> None: ...
