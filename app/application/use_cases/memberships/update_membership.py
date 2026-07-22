import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import EntityNotFoundError, ForbiddenError, LastAdminError, ValidationError
from app.domain.repositories import MembershipRepository

logger = logging.getLogger(__name__)

_ALLOWED_STATUS_TRANSITIONS = frozenset((MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED))


@dataclass
class UpdateMembershipInput:
    library_id: UUID
    requester_library_id: UUID
    target_user_id: UUID
    role: UserRole | None = None
    status: MembershipStatus | None = None


class UpdateMembershipUseCase:
    """Changes a member's role and/or toggles active/suspended for one
    library. Revoking a membership entirely and accepting a pending invite
    are separate use cases — this one only covers the two reversible states
    an admin flips day-to-day."""

    def __init__(self, membership_repo: MembershipRepository):
        self._membership_repo = membership_repo

    async def execute(self, input: UpdateMembershipInput) -> None:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot update another library's membership")

        if input.status is not None and input.status not in _ALLOWED_STATUS_TRANSITIONS:
            raise ValidationError("status must be 'active' or 'suspended'")

        membership = await self._membership_repo.find_by_user_and_library(input.target_user_id, input.library_id)
        if membership is None or membership.status == MembershipStatus.REVOKED:
            raise EntityNotFoundError("Membership not found")

        # Child accounts only come from the dedicated create-child flow (fake
        # @kids.jinbocho.internal email, guardian-routed password resets) —
        # this generic endpoint may demote a child to a normal role (e.g. once
        # they're old enough for their own email) but must never promote an
        # existing member to "child", which would skip that setup entirely.
        if input.role == UserRole.CHILD and membership.role != UserRole.CHILD:
            raise ForbiddenError("Child accounts can only be created via the dedicated child-account flow")

        demoting_admin = input.role is not None and input.role != UserRole.ADMIN
        suspending = input.status == MembershipStatus.SUSPENDED
        if membership.role == UserRole.ADMIN and membership.status == MembershipStatus.ACTIVE and (
            demoting_admin or suspending
        ):
            siblings = await self._membership_repo.lock_active_admins(input.library_id)
            other_active_admins = any(
                s.user_id != input.target_user_id and s.role == UserRole.ADMIN for s in siblings
            )
            if not other_active_admins:
                raise LastAdminError("Cannot demote or suspend the library's last active admin")

        if input.role is not None:
            membership.role = input.role
        if input.status is not None:
            membership.status = input.status

        await self._membership_repo.save(membership)
        logger.info("Membership of user %s in library %s updated", input.target_user_id, input.library_id)
