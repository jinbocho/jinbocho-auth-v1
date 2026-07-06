from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Library
from app.domain.repositories import LibraryRepository
from app.infrastructure.models import LibraryModel


class SQLAlchemyLibraryRepository(LibraryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: LibraryModel) -> Library:
        return Library(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, library: Library) -> Library:
        model = LibraryModel(
            id=library.id,
            name=library.name,
            description=library.description,
            created_at=library.created_at,
            updated_at=library.updated_at,
        )
        # merge upserts by primary key: INSERT for a new library, UPDATE for an
        # existing one. Plain add() would always INSERT and violate the PK on update.
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

    async def find_by_id(self, id: UUID) -> Library | None:
        result = await self._session.execute(select(LibraryModel).where(LibraryModel.id == id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(LibraryModel, id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
