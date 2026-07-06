import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import MembershipStatus
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import MembershipRepository

logger = logging.getLogger(__name__)


@dataclass
class DeclineInvitationInput:
    user_id: UUID
    library_id: UUID


class DeclineInvitationUseCase:
    """Lets the invited user turn down a pending invite. Ends in the same
    `revoked` state an admin-initiated removal would — from the system's
    perspective "declined by the invitee" and "removed by an admin" are both
    just "this membership is over", and re-inviting later is already
    permitted for any non-revoked... i.e. revoked membership (see
    InviteMemberUseCase's already_member check)."""

    def __init__(self, membership_repo: MembershipRepository):
        self._membership_repo = membership_repo

    async def execute(self, input: DeclineInvitationInput) -> None:
        membership = await self._membership_repo.find_by_user_and_library(input.user_id, input.library_id)
        if membership is None or membership.status != MembershipStatus.INVITED:
            raise EntityNotFoundError("No pending invitation for this library")

        membership.status = MembershipStatus.REVOKED
        membership.updated_at = datetime.now(timezone.utc)
        await self._membership_repo.save(membership)
        logger.info("User %s declined invitation to library %s", input.user_id, input.library_id)
