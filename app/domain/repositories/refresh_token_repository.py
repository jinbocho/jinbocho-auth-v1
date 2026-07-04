from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def save(self, token: RefreshToken) -> RefreshToken: ...

    @abstractmethod
    async def find_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, token_hash: str) -> None: ...

    @abstractmethod
    async def revoke_all_for_users(self, user_ids: list[UUID]) -> int: ...

    @abstractmethod
    async def cleanup_expired(self) -> int: ...
