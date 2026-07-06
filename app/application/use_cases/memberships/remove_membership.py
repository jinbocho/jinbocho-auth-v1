import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import EntityNotFoundError, LastAdminError
from app.domain.repositories import MembershipRepository

logger = logging.getLogger(__name__)


@dataclass
class RemoveMembershipInput:
    library_id: UUID
    target_user_id: UUID


class RemoveMembershipUseCase:
    """Revokes a membership permanently (soft-delete: status -> revoked, row
    kept for audit). Does not touch the global User account — they may still
    have other library memberships."""

    def __init__(self, membership_repo: MembershipRepository):
        self._membership_repo = membership_repo

    async def execute(self, input: RemoveMembershipInput) -> None:
        membership = await self._membership_repo.find_by_user_and_library(input.target_user_id, input.library_id)
        if membership is None or membership.status == MembershipStatus.REVOKED:
            raise EntityNotFoundError("Membership not found")

        if membership.role == UserRole.ADMIN and membership.status == MembershipStatus.ACTIVE:
            siblings = await self._membership_repo.find_by_library(input.library_id, [MembershipStatus.ACTIVE])
            other_active_admins = any(s.user_id != input.target_user_id and s.role == UserRole.ADMIN for s in siblings)
            if not other_active_admins:
                raise LastAdminError("Cannot remove the library's last active admin")

        membership.status = MembershipStatus.REVOKED
        membership.updated_at = datetime.now(timezone.utc)
        await self._membership_repo.save(membership)
        logger.info("Membership of user %s in library %s revoked", input.target_user_id, input.library_id)
