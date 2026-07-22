from dataclasses import dataclass
from uuid import UUID

from app.domain.entities import MembershipStatus, UserRole
from app.domain.exceptions import ForbiddenError
from app.domain.repositories import MembershipRepository, UserRepository

_MIN_QUERY_CHARS = 2


@dataclass
class SearchMembersInput:
    library_id: UUID
    requester_library_id: UUID
    query: str
    limit: int = 3


@dataclass
class MemberSearchResult:
    user_id: UUID
    full_name: str
    email: str
    role: UserRole
    avatar_url: str | None


@dataclass
class SearchMembersOutput:
    results: list[MemberSearchResult]


class SearchMembersUseCase:
    """Typeahead search across the active members of one library — powers
    "lend this book to a Jinbocho user". Filters in Python over
    find_by_library's result rather than adding a new cross-model SQL join:
    a library's roster is small by construction (a household, not a
    platform-wide user base — contrast with SearchUsersUseCase, which does
    need a real query since it scans every account in the system)."""

    def __init__(self, membership_repo: MembershipRepository, user_repo: UserRepository):
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    async def execute(self, input: SearchMembersInput) -> SearchMembersOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot search another library's members")

        needle = input.query.strip().lower()
        if len(needle) < _MIN_QUERY_CHARS:
            return SearchMembersOutput(results=[])

        memberships = await self._membership_repo.find_by_library(input.library_id, [MembershipStatus.ACTIVE])
        matches: list[MemberSearchResult] = []
        for m in memberships:
            user = await self._user_repo.find_by_id(m.user_id)
            if user is None:
                continue
            if needle in user.full_name.lower() or needle in user.email.lower():
                matches.append(
                    MemberSearchResult(
                        user_id=user.id, full_name=user.full_name, email=user.email,
                        role=m.role, avatar_url=user.avatar_url,
                    )
                )
        matches.sort(key=lambda r: r.full_name.lower())
        return SearchMembersOutput(results=matches[: input.limit])
