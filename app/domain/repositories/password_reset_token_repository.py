from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities import PasswordResetToken


class PasswordResetTokenRepository(ABC):
    @abstractmethod
    async def save(self, token: PasswordResetToken) -> PasswordResetToken: ...

    @abstractmethod
    async def find_by_token_hash(self, token_hash: str) -> PasswordResetToken | None: ...

    @abstractmethod
    async def mark_used(self, token_id: UUID, used_at: datetime) -> None: ...

    @abstractmethod
    async def invalidate_pending(self, user_id: UUID, purpose: str, used_at: datetime) -> None:
        """Mark every unused token of this purpose for this user as used,
        so a resent invite link makes any earlier one stop working."""
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Delete tokens that are expired or already used. Returns the count removed."""
        ...
