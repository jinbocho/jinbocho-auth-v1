from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RefreshToken
from app.domain.repositories import RefreshTokenRepository
from app.infrastructure.models import RefreshTokenModel


class SQLAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
        )

    async def save(self, token: RefreshToken) -> RefreshToken:
        model = RefreshTokenModel(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            created_at=token.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def revoke(self, token_hash: str) -> bool:
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
        return result.rowcount > 0

    async def revoke_all_for_users(self, user_ids: list[UUID]) -> int:
        if not user_ids:
            return 0
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id.in_(user_ids), RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
        return result.rowcount

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < now)
        )
        await self._session.flush()
        return result.rowcount
