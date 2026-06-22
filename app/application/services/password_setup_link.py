import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from app.application.services.token_service import TokenService
from app.domain.entities import PasswordResetToken, User
from app.domain.repositories import PasswordResetTokenRepository
from app.infrastructure.email.email_sender import EmailSender


async def issue_password_setup_link(
    user: User,
    purpose: str,
    expire_minutes: int,
    reset_token_repo: PasswordResetTokenRepository,
    email_sender: EmailSender,
    token_service: TokenService,
    frontend_base_url: str,
) -> None:
    """Create a single-use token and email the link to set a password.

    Shared by the "forgot password" flow (purpose="reset") and the
    admin-invites-a-user flow (purpose="invite") — they differ only in who
    triggers it, the expiry window, and the email copy.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = token_service.hash_token(raw_token)
    now = datetime.now(timezone.utc)

    await reset_token_repo.save(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=expire_minutes),
            purpose=purpose,
        )
    )

    link = f"{frontend_base_url}/reset-password?token={raw_token}&mode={purpose}"
    await asyncio.to_thread(
        email_sender.send_password_setup_link, user.email, link, purpose=purpose, language=user.language
    )
