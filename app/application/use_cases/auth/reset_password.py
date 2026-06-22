from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.services import TokenService
from app.domain.exceptions import InvalidResetTokenError, ResetTokenAlreadyUsedError
from app.domain.repositories import PasswordResetTokenRepository, UserRepository
from app.domain.services import PasswordHasher


@dataclass
class ResetPasswordInput:
    token: str
    new_password: str


class ResetPasswordUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._token_service = token_service
        self._password_hasher = password_hasher

    async def execute(self, input: ResetPasswordInput) -> None:
        token_hash = self._token_service.hash_token(input.token)
        token = await self._reset_token_repo.find_by_token_hash(token_hash)

        if not token:
            raise InvalidResetTokenError("Invalid or expired reset token")

        now = datetime.now(timezone.utc)

        if token.used_at is not None:
            raise ResetTokenAlreadyUsedError("Reset token has already been used")

        # Compare timezone-aware datetimes safely.
        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise InvalidResetTokenError("Reset token has expired")

        user = await self._user_repo.find_by_id(token.user_id)
        if not user or not user.is_active:
            raise InvalidResetTokenError("Invalid or expired reset token")

        user.password_hash = self._password_hasher.hash(input.new_password)
        user.updated_at = now
        await self._user_repo.save(user)
        await self._reset_token_repo.mark_used(token.id, now)
