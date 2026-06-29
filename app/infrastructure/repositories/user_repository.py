from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Language, ThemeMode, ThemeName, User, UserRole
from app.domain.repositories import UserRepository
from app.infrastructure.models import UserModel


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
            role=UserRole(model.role),
            is_active=model.is_active,
            annual_reading_goal=model.annual_reading_goal,
            language=Language(model.language) if model.language else None,
            theme_name=ThemeName(model.theme_name) if model.theme_name else None,
            theme_mode=ThemeMode(model.theme_mode) if model.theme_mode else None,
            avatar_url=model.avatar_url,
            password_set_at=model.password_set_at,
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
            annual_reading_goal=user.annual_reading_goal,
            language=user.language,
            theme_name=user.theme_name,
            theme_mode=user.theme_mode,
            avatar_url=user.avatar_url,
            password_set_at=user.password_set_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        # merge() performs an upsert: insert for new entities, update for
        # entities already present in the database (e.g. UpdateUserUseCase).
        # add() would raise on a duplicate primary key when updating.
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_id(self, id: UUID) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_family(self, family_id: UUID) -> list[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.family_id == family_id).order_by(UserModel.full_name)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def delete(self, id: UUID) -> None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == id))
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
