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
