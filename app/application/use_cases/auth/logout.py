from dataclasses import dataclass

from app.application.services import TokenService
from app.domain.repositories import RefreshTokenRepository


@dataclass
class LogoutInput:
    refresh_token: str


class LogoutUseCase:
    def __init__(self, refresh_token_repo: RefreshTokenRepository, token_service: TokenService):
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service

    async def execute(self, input: LogoutInput) -> None:
        token_hash = self._token_service.hash_token(input.refresh_token)
        await self._refresh_token_repo.revoke(token_hash)
