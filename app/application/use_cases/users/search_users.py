import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)

_MIN_QUERY_CHARS = 4


@dataclass
class SearchUsersInput:
    query: str
    exclude_library_id: UUID
    requested_by: UUID
    limit: int = 3


@dataclass
class UserSearchResult:
    user_id: UUID
    full_name: str
    email: str


@dataclass
class SearchUsersOutput:
    results: list[UserSearchResult]


class SearchUsersUseCase:
    """Cross-tenant typeahead for inviting an existing Jinbocho account into
    a *different* library. Deliberately the most restrictive search in the
    system: a higher minimum query length than SearchMembersUseCase (4 vs 2),
    audit-logged, and — enforced by the caller, not here — admin-only and
    rate-limited. See jinbocho-docs/architecture/user-search-plan.md §6 for
    the privacy reasoning behind these choices."""

    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: SearchUsersInput) -> SearchUsersOutput:
        needle = input.query.strip()
        if len(needle) < _MIN_QUERY_CHARS:
            return SearchUsersOutput(results=[])

        users = await self._user_repo.search_active_excluding_library(
            needle, input.exclude_library_id, input.limit
        )
        logger.info(
            "Admin %s searched global users (query length %d) for library %s",
            input.requested_by, len(needle), input.exclude_library_id,
        )
        return SearchUsersOutput(
            results=[UserSearchResult(user_id=u.id, full_name=u.full_name, email=u.email) for u in users]
        )
