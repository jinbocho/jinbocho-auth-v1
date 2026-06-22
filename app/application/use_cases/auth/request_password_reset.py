from dataclasses import dataclass

from app.application.services import TokenService, issue_password_setup_link
from app.config import settings
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
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender
        self._token_service = token_service

    async def execute(self, input: RequestPasswordResetInput) -> None:
        user = await self._user_repo.find_by_email(input.email)
        # Always return silently to prevent email enumeration.
        if not user or not user.is_active:
            return

        await issue_password_setup_link(
            user,
            purpose="reset",
            expire_minutes=settings.password_reset_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
            token_service=self._token_service,
            frontend_base_url=settings.frontend_base_url,
        )
