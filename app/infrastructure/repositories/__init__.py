from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Family, User
from app.domain.repositories import FamilyRepository, UserRepository
from app.infrastructure.models import FamilyModel, UserModel


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


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            family_id=model.family_id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            role=model.role,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            family_id=user.family_id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_email(self, email: str):
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_id(self, id):
        result = await self._session.execute(select(UserModel).where(UserModel.id == id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
