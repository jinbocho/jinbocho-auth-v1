from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def save(self, token: RefreshToken) -> RefreshToken: ...

    @abstractmethod
    async def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]: ...

    @abstractmethod
    async def revoke(self, token_hash: str) -> None: ...

    @abstractmethod
    async def cleanup_expired(self) -> int: ...
