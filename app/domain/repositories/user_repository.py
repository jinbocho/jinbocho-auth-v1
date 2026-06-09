from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> User: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> Optional[User]: ...

    @abstractmethod
    async def find_by_family(self, family_id: UUID) -> list[User]: ...

    @abstractmethod
    async def delete(self, id: UUID) -> None: ...
