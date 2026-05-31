from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Family
from app.domain.repositories import FamilyRepository
from app.infrastructure.models import FamilyModel


class SQLAlchemyFamilyRepository(FamilyRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: FamilyModel) -> Family:
        return Family(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, family: Family) -> Family:
        model = FamilyModel(
            id=family.id,
            name=family.name,
            description=family.description,
            created_at=family.created_at,
            updated_at=family.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_id(self, id):
        result = await self._session.execute(select(FamilyModel).where(FamilyModel.id == id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
