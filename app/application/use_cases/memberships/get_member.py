from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import MembershipRepository, UserRepository


@dataclass
class GetMemberInput:
    library_id: UUID
    requester_library_id: UUID
    user_id: UUID


@dataclass
class GetMemberOutput:
    user_id: UUID
    full_name: str
    email: str
    role: UserRole
    avatar_url: str | None
    joined_at: datetime | None
    birth_year: int | None


class GetMemberUseCase:
    """Single-member lookup, open to any active member of the library — not
    admin-only like ListMembersUseCase (the full roster, used for the admin
    management view). This powers clicking a fellow member's name from
    somewhere else in the app (e.g. a loan's borrower) to see their basic
    profile — a much lower-sensitivity operation than roster management."""

    def __init__(self, membership_repo: MembershipRepository, user_repo: UserRepository):
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    async def execute(self, input: GetMemberInput) -> GetMemberOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot view another library's member")

        membership = await self._membership_repo.find_by_user_and_library(input.user_id, input.library_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise EntityNotFoundError("Member not found")

        user = await self._user_repo.find_by_id(input.user_id)
        if user is None:
            raise EntityNotFoundError("Member not found")

        return GetMemberOutput(
            user_id=user.id, full_name=user.full_name, email=user.email,
            role=membership.role, avatar_url=user.avatar_url, joined_at=membership.joined_at,
            birth_year=user.birth_year,
        )
