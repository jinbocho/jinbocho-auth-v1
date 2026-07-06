from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.repositories import MembershipRepository, UserRepository


@dataclass
class ListMembersInput:
    library_id: UUID


@dataclass
class MemberSummary:
    membership_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: UserRole
    status: MembershipStatus
    joined_at: datetime | None
    last_accessed_at: datetime | None
    avatar_url: str | None = None


@dataclass
class ListMembersOutput:
    members: list[MemberSummary]


class ListMembersUseCase:
    def __init__(self, membership_repo: MembershipRepository, user_repo: UserRepository):
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    async def execute(self, input: ListMembersInput) -> ListMembersOutput:
        memberships = await self._membership_repo.find_by_library(
            input.library_id, [MembershipStatus.ACTIVE, MembershipStatus.INVITED, MembershipStatus.SUSPENDED]
        )
        members = []
        for m in memberships:
            user = await self._user_repo.find_by_id(m.user_id)
            if user is None:
                continue
            members.append(
                MemberSummary(
                    membership_id=m.id,
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=m.role,
                    status=m.status,
                    joined_at=m.joined_at,
                    last_accessed_at=m.last_accessed_at,
                    avatar_url=user.avatar_url,
                )
            )
        return ListMembersOutput(members=members)
