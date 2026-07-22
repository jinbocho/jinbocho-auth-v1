from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import LibraryMembership, MembershipStatus, UserRole
from app.domain.repositories import MembershipRepository
from app.infrastructure.models import LibraryMembershipModel


class SQLAlchemyMembershipRepository(MembershipRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: LibraryMembershipModel) -> LibraryMembership:
        return LibraryMembership(
            id=model.id,
            user_id=model.user_id,
            library_id=model.library_id,
            role=UserRole(model.role),
            status=MembershipStatus(model.status),
            invited_by=model.invited_by,
            invited_at=model.invited_at,
            joined_at=model.joined_at,
            last_accessed_at=model.last_accessed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, membership: LibraryMembership) -> LibraryMembership:
        model = LibraryMembershipModel(
            id=membership.id,
            user_id=membership.user_id,
            library_id=membership.library_id,
            role=membership.role.value,
            status=membership.status.value,
            invited_by=membership.invited_by,
            invited_at=membership.invited_at,
            joined_at=membership.joined_at,
            last_accessed_at=membership.last_accessed_at,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

    async def find_by_id(self, id: UUID) -> LibraryMembership | None:
        result = await self._session.execute(select(LibraryMembershipModel).where(LibraryMembershipModel.id == id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_user_and_library(self, user_id: UUID, library_id: UUID) -> LibraryMembership | None:
        result = await self._session.execute(
            select(LibraryMembershipModel).where(
                LibraryMembershipModel.user_id == user_id, LibraryMembershipModel.library_id == library_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_user(
        self, user_id: UUID, statuses: list[MembershipStatus] | None = None
    ) -> list[LibraryMembership]:
        query = select(LibraryMembershipModel).where(LibraryMembershipModel.user_id == user_id)
        if statuses:
            query = query.where(LibraryMembershipModel.status.in_([s.value for s in statuses]))
        result = await self._session.execute(query.order_by(LibraryMembershipModel.last_accessed_at.desc()))
        return [self._to_entity(model) for model in result.scalars().all()]

    async def find_by_library(
        self, library_id: UUID, statuses: list[MembershipStatus] | None = None
    ) -> list[LibraryMembership]:
        query = select(LibraryMembershipModel).where(LibraryMembershipModel.library_id == library_id)
        if statuses:
            query = query.where(LibraryMembershipModel.status.in_([s.value for s in statuses]))
        result = await self._session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def lock_active_admins(self, library_id: UUID) -> list[LibraryMembership]:
        result = await self._session.execute(
            select(LibraryMembershipModel)
            .where(
                LibraryMembershipModel.library_id == library_id,
                LibraryMembershipModel.status == MembershipStatus.ACTIVE.value,
            )
            .with_for_update()
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(LibraryMembershipModel, id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
