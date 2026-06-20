from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.entities import Family


class FamilyRepository(ABC):
    @abstractmethod
    async def save(self, family: Family) -> Family: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> Optional[Family]: ...

    @abstractmethod
    async def delete(self, id: UUID) -> None:
        """Deletes the family — the DB cascades to every user (and from
        there, every refresh/password-reset token). Used by the account
        deletion flow, after the caller's own confirmation/password check."""
        ...
