import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.application.ports import EmailService
from app.application.services import TokenService
from app.domain.exceptions import EmailAlreadyRegisteredError, EntityNotFoundError, IncorrectPasswordError
from app.domain.entities import EmailChangeToken
from app.domain.repositories import EmailChangeTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class RequestEmailChangeInput:
    user_id: UUID
    new_email: str
    current_password: str


class RequestEmailChangeUseCase:
    """Starts a verify-before-apply email change: the user's row is left
    untouched, and the confirmation link is sent to the NEW address (not the
    current one) — proving the user actually controls it before the account's
    email of record changes, so a typo can never lock them out silently."""

    def __init__(
        self,
        user_repo: UserRepository,
        email_change_token_repo: EmailChangeTokenRepository,
        email_sender: EmailService,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        expire_minutes: int,
        frontend_base_url: str,
    ):
        self._user_repo = user_repo
        self._email_change_token_repo = email_change_token_repo
        self._email_sender = email_sender
        self._token_service = token_service
        self._password_hasher = password_hasher
        self._expire_minutes = expire_minutes
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: RequestEmailChangeInput) -> None:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user:
            raise EntityNotFoundError("User not found")

        # Re-authentication: a JWT alone (e.g. stolen/XSS'd) must not be enough
        # to redirect the account to an attacker-controlled address.
        if not self._password_hasher.verify(input.current_password, user.password_hash):
            raise IncorrectPasswordError("Incorrect password")

        # Normalized once and reused for the dedup check, stored token, and
        # verification email — otherwise "user@x.com" and "User@x.com" pass
        # the duplicate check as distinct accounts for the same real mailbox
        # (confirmed via pentest).
        new_email = input.new_email.strip().lower()
        if new_email == user.email:
            return

        existing = await self._user_repo.find_by_email(new_email)
        if existing and existing.id != user.id and existing.is_active:
            raise EmailAlreadyRegisteredError("Email already registered")

        now = datetime.now(timezone.utc)
        await self._email_change_token_repo.invalidate_pending(user.id, now)

        raw_token = secrets.token_urlsafe(32)
        token_hash = self._token_service.hash_token(raw_token)
        await self._email_change_token_repo.save(
            EmailChangeToken(
                user_id=user.id,
                new_email=new_email,
                token_hash=token_hash,
                expires_at=now + timedelta(minutes=self._expire_minutes),
            )
        )

        language = user.language.value if user.language else None
        link = f"{self._frontend_base_url}/confirm-email-change?token={raw_token}"
        await asyncio.to_thread(
            self._email_sender.send_email_change_verification,
            new_email, link,
            language=language,
        )
        # Sent to the OLD address too — informational only, no action link —
        # so a hijacked session can't silently redirect the account without
        # the real owner having any way to notice.
        await asyncio.to_thread(
            self._email_sender.send_email_change_requested_notice,
            user.email, new_email,
            f"{self._frontend_base_url}/forgot-password",
            language=language,
        )
        logger.info("Email change requested for user %s", user.id)
