from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import EmailChangeToken
from app.domain.repositories import EmailChangeTokenRepository
from app.infrastructure.models import EmailChangeTokenModel


class SQLAlchemyEmailChangeTokenRepository(EmailChangeTokenRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: EmailChangeTokenModel) -> EmailChangeToken:
        return EmailChangeToken(
            id=model.id,
            user_id=model.user_id,
            new_email=model.new_email,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            used_at=model.used_at,
            created_at=model.created_at,
        )

    async def save(self, token: EmailChangeToken) -> EmailChangeToken:
        model = EmailChangeTokenModel(
            id=token.id,
            user_id=token.user_id,
            new_email=token.new_email,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            used_at=token.used_at,
            created_at=token.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_token_hash(self, token_hash: str) -> EmailChangeToken | None:
        result = await self._session.execute(
            select(EmailChangeTokenModel).where(EmailChangeTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def mark_used(self, token_id: UUID, used_at: datetime) -> bool:
        result = await self._session.execute(
            update(EmailChangeTokenModel)
            .where(EmailChangeTokenModel.id == token_id, EmailChangeTokenModel.used_at.is_(None))
            .values(used_at=used_at)
        )
        await self._session.flush()
        return result.rowcount > 0

    async def invalidate_pending(self, user_id: UUID, used_at: datetime) -> None:
        await self._session.execute(
            update(EmailChangeTokenModel)
            .where(
                EmailChangeTokenModel.user_id == user_id,
                EmailChangeTokenModel.used_at.is_(None),
            )
            .values(used_at=used_at)
        )
        await self._session.flush()
