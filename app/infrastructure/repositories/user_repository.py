from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Language, MembershipStatus, ThemeMode, ThemeName, User, UserRole
from app.domain.repositories import UserRepository
from app.infrastructure.models import LibraryMembershipModel, UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            library_id=model.library_id,
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
            consent_privacy_version=model.consent_privacy_version,
            consent_terms_version=model.consent_terms_version,
            consent_at=model.consent_at,
            last_selected_library_id=model.last_selected_library_id,
            tour_completed_at=model.tour_completed_at,
            guardian_email=model.guardian_email,
            birth_year=model.birth_year,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            library_id=user.library_id,
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
            consent_privacy_version=user.consent_privacy_version,
            consent_terms_version=user.consent_terms_version,
            consent_at=user.consent_at,
            last_selected_library_id=user.last_selected_library_id,
            tour_completed_at=user.tour_completed_at,
            guardian_email=user.guardian_email,
            birth_year=user.birth_year,
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

    async def find_by_library(self, library_id: UUID) -> list[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.library_id == library_id).order_by(UserModel.full_name)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def lock_active_admins(self, library_id: UUID) -> list[User]:
        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.library_id == library_id, UserModel.is_active.is_(True))
            .with_for_update()
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def search_active_excluding_library(
        self, query: str, exclude_library_id: UUID, limit: int
    ) -> list[User]:
        needle = f"%{query}%"
        already_member = (
            select(LibraryMembershipModel.user_id)
            .where(
                LibraryMembershipModel.library_id == exclude_library_id,
                LibraryMembershipModel.status != MembershipStatus.REVOKED.value,
            )
        )
        result = await self._session.execute(
            select(UserModel)
            .where(
                UserModel.is_active.is_(True),
                UserModel.id.not_in(already_member),
                (UserModel.full_name.ilike(needle) | UserModel.email.ilike(needle)),
            )
            .order_by(UserModel.full_name)
            .limit(limit)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def delete(self, id: UUID) -> None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == id))
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
