from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities import EmailChangeToken


class EmailChangeTokenRepository(ABC):
    @abstractmethod
    async def save(self, token: EmailChangeToken) -> EmailChangeToken: ...

    @abstractmethod
    async def find_by_token_hash(self, token_hash: str) -> EmailChangeToken | None: ...

    @abstractmethod
    async def mark_used(self, token_id: UUID, used_at: datetime) -> None: ...

    @abstractmethod
    async def invalidate_pending(self, user_id: UUID, used_at: datetime) -> None:
        """Mark every unused token for this user as used, so requesting a
        new email change makes any earlier unconfirmed link stop working."""
        ...
