from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def save(self, token: RefreshToken) -> RefreshToken: ...

    @abstractmethod
    async def find_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, token_hash: str) -> bool:
        """Atomically revoke the token iff it isn't already revoked, and
        report whether this call was the one that did it. Must be a single
        conditional UPDATE (`WHERE revoked_at IS NULL`), not a separate
        read-then-write, so concurrent callers racing on the same token can't
        all observe "not revoked yet" and all succeed (see RefreshTokenUseCase,
        which relies on this to make token rotation exactly-once)."""
        ...

    @abstractmethod
    async def revoke_all_for_users(self, user_ids: list[UUID]) -> int: ...

    @abstractmethod
    async def cleanup_expired(self) -> int: ...
