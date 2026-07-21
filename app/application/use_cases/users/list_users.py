from dataclasses import dataclass
from uuid import UUID

from app.domain.entities import MembershipStatus, User
from app.domain.repositories import MembershipRepository, UserRepository

_ROSTER_STATUSES = [MembershipStatus.ACTIVE, MembershipStatus.INVITED, MembershipStatus.SUSPENDED]


@dataclass
class ListUsersInput:
    library_id: UUID


@dataclass
class ListUsersOutput:
    users: list[User]


class ListUsersUseCase:
    """Membership-based, like ListMembersUseCase, but open to any authenticated
    library member rather than admin-only — this backs pickers (e.g. book
    owner) that any editor needs to populate. Excludes REVOKED memberships so
    a removed member stops appearing here, matching what admins see on the
    Users page."""

    def __init__(self, user_repo: UserRepository, membership_repo: MembershipRepository):
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, input: ListUsersInput) -> ListUsersOutput:
        memberships = await self._membership_repo.find_by_library(input.library_id, _ROSTER_STATUSES)
        users = []
        for m in memberships:
            user = await self._user_repo.find_by_id(m.user_id)
            if user is not None:
                users.append(user)
        return ListUsersOutput(users=users)
