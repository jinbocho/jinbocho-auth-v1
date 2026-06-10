import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from passlib.context import CryptContext  # type: ignore[import-untyped]

from app.domain.repositories import PasswordResetTokenRepository, UserRepository


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class ResetPasswordInput:
    token: str
    new_password: str


class ResetPasswordUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo

    async def execute(self, input: ResetPasswordInput) -> None:
        token_hash = hashlib.sha256(input.token.encode()).hexdigest()
        token = await self._reset_token_repo.find_by_token_hash(token_hash)

        if not token:
            raise ValueError("Invalid or expired reset token")

        now = datetime.now(timezone.utc)

        if token.used_at is not None:
            raise ValueError("Reset token has already been used")

        # Compare timezone-aware datetimes safely.
        expires = token.expires_at
        if expires.tzinfo is None:
            from datetime import timezone as _tz
            expires = expires.replace(tzinfo=_tz.utc)
        if expires < now:
            raise ValueError("Reset token has expired")

        user = await self._user_repo.find_by_id(token.user_id)
        if not user or not user.is_active:
            raise ValueError("Invalid or expired reset token")

        user.password_hash = pwd_context.hash(input.new_password)
        user.updated_at = now
        await self._user_repo.save(user)
        await self._reset_token_repo.mark_used(token.id, now)
