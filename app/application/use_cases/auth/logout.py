from dataclasses import dataclass

from app.application.services import TokenService
from app.config import settings
from app.domain.repositories import RefreshTokenRepository


@dataclass
class LogoutInput:
    refresh_token: str


class LogoutUseCase:
    def __init__(self, refresh_token_repo: RefreshTokenRepository):
        self._refresh_token_repo = refresh_token_repo

    async def execute(self, input: LogoutInput) -> None:
        token_service = TokenService(settings)
        token_hash = token_service.hash_token(input.refresh_token)
        await self._refresh_token_repo.revoke(token_hash)
