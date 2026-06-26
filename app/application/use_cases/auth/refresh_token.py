import logging
from dataclasses import dataclass
from datetime import timedelta

from app.application.services import TokenService
from app.domain.entities import RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from app.domain.repositories import RefreshTokenRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class RefreshTokenInput:
    refresh_token: str


@dataclass
class RefreshTokenOutput:
    access_token: str
    refresh_token: str


class RefreshTokenUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service

    async def execute(self, input: RefreshTokenInput) -> RefreshTokenOutput:
        now = self._token_service.utcnow()
        token_hash = self._token_service.hash_token(input.refresh_token)
        stored_token = await self._refresh_token_repo.find_by_hash(token_hash)

        if not stored_token:
            raise InvalidCredentialsError("Invalid refresh token")

        self._token_service.validate_token_not_revoked(stored_token, now)

        user = await self._user_repo.find_by_id(stored_token.user_id)
        if not user:
            raise InvalidCredentialsError("Invalid refresh token")
        if not user.is_active:
            raise InactiveUserError("User is inactive")

        await self._refresh_token_repo.revoke(token_hash)

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, str(user.family_id), user.role
        )
        new_refresh_token = self._token_service.create_refresh_token()

        new_token_entity = RefreshToken(
            user_id=user.id,
            token_hash=self._token_service.hash_token(new_refresh_token),
            expires_at=now + timedelta(days=self._token_service.refresh_token_expire_days),
        )
        await self._refresh_token_repo.save(new_token_entity)
        logger.debug("Refresh token rotated for user %s", user.id)
        return RefreshTokenOutput(access_token=access_token, refresh_token=new_refresh_token)
