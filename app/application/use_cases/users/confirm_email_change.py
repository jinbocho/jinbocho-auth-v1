import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.services import TokenService
from app.domain.exceptions import (
    EmailAlreadyRegisteredError,
    EmailChangeTokenAlreadyUsedError,
    InvalidEmailChangeTokenError,
)
from app.domain.repositories import EmailChangeTokenRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class ConfirmEmailChangeInput:
    token: str


class ConfirmEmailChangeUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        email_change_token_repo: EmailChangeTokenRepository,
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._email_change_token_repo = email_change_token_repo
        self._token_service = token_service

    async def execute(self, input: ConfirmEmailChangeInput) -> None:
        token_hash = self._token_service.hash_token(input.token)
        token = await self._email_change_token_repo.find_by_token_hash(token_hash)

        if not token:
            logger.warning("Email change confirmation attempted with unknown token")
            raise InvalidEmailChangeTokenError("Invalid or expired email change token")

        now = datetime.now(timezone.utc)

        if token.used_at is not None:
            raise EmailChangeTokenAlreadyUsedError("Email change token has already been used")

        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise InvalidEmailChangeTokenError("Email change token has expired")

        user = await self._user_repo.find_by_id(token.user_id)
        if not user:
            raise InvalidEmailChangeTokenError("Invalid or expired email change token")

        # Re-check uniqueness: another account could have claimed this
        # address between the request and this confirmation.
        existing = await self._user_repo.find_by_email(token.new_email)
        if existing and existing.id != user.id:
            raise EmailAlreadyRegisteredError("Email already registered")

        user.email = token.new_email
        user.updated_at = now
        await self._user_repo.save(user)
        await self._email_change_token_repo.mark_used(token.id, now)
        logger.info("Email change confirmed for user %s", user.id)
