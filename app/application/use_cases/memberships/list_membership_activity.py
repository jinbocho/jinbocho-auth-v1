from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import ForbiddenError
from app.domain.repositories import MembershipRepository, UserRepository

MembershipActivityEvent = str  # "member_added" | "member_removed"


@dataclass
class ListMembershipActivityInput:
    library_id: UUID
    requester_library_id: UUID
    limit: int = 20


@dataclass
class MembershipActivityItem:
    user_id: UUID
    full_name: str
    avatar_url: str | None
    role: UserRole
    event: MembershipActivityEvent
    occurred_at: datetime


@dataclass
class ListMembershipActivityOutput:
    items: list[MembershipActivityItem]


class ListMembershipActivityUseCase:
    """Recent member-added/member-removed events for the dashboard activity
    feed. Unlike ListMembersUseCase (the admin roster), this deliberately
    includes REVOKED memberships — a removal only shows up in the feed
    because the row is soft-deleted, not hard-deleted."""

    def __init__(self, membership_repo: MembershipRepository, user_repo: UserRepository):
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    async def execute(self, input: ListMembershipActivityInput) -> ListMembershipActivityOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot view another library's membership activity")

        memberships = await self._membership_repo.find_by_library(input.library_id, statuses=None)

        items: list[MembershipActivityItem] = []
        for m in memberships:
            if m.status == MembershipStatus.REVOKED:
                event: MembershipActivityEvent = "member_removed"
                occurred_at = m.updated_at
            else:
                event = "member_added"
                # invited_at is unset for a library's founding admin — that
                # membership is created directly by RegisterLibraryUseCase,
                # not InviteMemberUseCase, with only joined_at set. created_at
                # is the final fallback and always present.
                occurred_at = m.invited_at or m.joined_at or m.created_at

            user = await self._user_repo.find_by_id(m.user_id)
            if user is None:
                continue

            items.append(
                MembershipActivityItem(
                    user_id=user.id,
                    full_name=user.full_name,
                    avatar_url=user.avatar_url,
                    role=m.role,
                    event=event,
                    occurred_at=occurred_at,
                )
            )

        items.sort(key=lambda i: i.occurred_at, reverse=True)
        return ListMembershipActivityOutput(items=items[: input.limit])
