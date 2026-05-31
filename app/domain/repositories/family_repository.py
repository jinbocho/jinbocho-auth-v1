from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.entities import Family


class FamilyRepository(ABC):
    @abstractmethod
    async def save(self, family: Family) -> Family: ...

    @abstractmethod
    async def find_by_id(self, id: UUID) -> Optional[Family]: ...
