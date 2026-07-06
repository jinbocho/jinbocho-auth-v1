from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import ForbiddenError
from app.domain.repositories import RefreshTokenRepository, UserRepository


@dataclass
class RevokeLibrarySessionsInput:
    library_id: UUID
    requester_library_id: UUID


@dataclass
class RevokeLibrarySessionsOutput:
    revoked_count: int


class RevokeLibrarySessionsUseCase:
    """Emergency response to a suspected credential leak: revokes every
    refresh token for every member of the library, forcing everyone to log in
    again on their next token refresh. Already-issued access tokens remain
    valid until they naturally expire (bounded by ACCESS_TOKEN_EXPIRE_MINUTES)
    — JWTs are stateless by design (ADR-008); immediate revocation of
    already-issued access tokens would require every service to hit the
    database on every request, which the architecture deliberately avoids."""

    def __init__(self, user_repo: UserRepository, refresh_token_repo: RefreshTokenRepository) -> None:
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo

    async def execute(self, inp: RevokeLibrarySessionsInput) -> RevokeLibrarySessionsOutput:
        if inp.library_id != inp.requester_library_id:
            raise ForbiddenError("Cannot revoke sessions for another library")
        users = await self._user_repo.find_by_library(inp.library_id)
        user_ids = [user.id for user in users]
        revoked_count = await self._refresh_token_repo.revoke_all_for_users(user_ids)
        return RevokeLibrarySessionsOutput(revoked_count=revoked_count)
