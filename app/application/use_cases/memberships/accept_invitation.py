import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import MembershipStatus
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import MembershipRepository

logger = logging.getLogger(__name__)


@dataclass
class AcceptInvitationInput:
    user_id: UUID
    library_id: UUID


class AcceptInvitationUseCase:
    """Lets the invited user (not an admin) turn their own `invited`
    membership into `active` — the F5 flow in the plan (invito accettato ->
    nuova membership attiva)."""

    def __init__(self, membership_repo: MembershipRepository):
        self._membership_repo = membership_repo

    async def execute(self, input: AcceptInvitationInput) -> None:
        membership = await self._membership_repo.find_by_user_and_library(input.user_id, input.library_id)
        if membership is None or membership.status != MembershipStatus.INVITED:
            raise EntityNotFoundError("No pending invitation for this library")

        membership.status = MembershipStatus.ACTIVE
        membership.joined_at = datetime.now(timezone.utc)
        await self._membership_repo.save(membership)
        logger.info("User %s accepted invitation to library %s", input.user_id, input.library_id)
