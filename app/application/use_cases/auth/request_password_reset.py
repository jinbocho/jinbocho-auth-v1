import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.domain.entities import PasswordResetToken
from app.domain.repositories import PasswordResetTokenRepository, UserRepository
from app.infrastructure.email.email_sender import EmailSender


@dataclass
class RequestPasswordResetInput:
    email: str


class RequestPasswordResetUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailSender,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender

    async def execute(self, input: RequestPasswordResetInput) -> None:
        user = await self._user_repo.find_by_email(input.email)
        # Always return silently to prevent email enumeration.
        if not user or not user.is_active:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        entity = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
        await self._reset_token_repo.save(entity)

        reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
        self._email_sender.send_password_reset(user.email, reset_link, language=user.language)
