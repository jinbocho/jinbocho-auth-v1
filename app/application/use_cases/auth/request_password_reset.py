import logging
from dataclasses import dataclass

from app.application.ports import EmailService
from app.application.services import TokenService, issue_password_setup_link
from app.domain.repositories import PasswordResetTokenRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class RequestPasswordResetInput:
    email: str


class RequestPasswordResetUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailService,
        token_service: TokenService,
        password_reset_expire_minutes: int,
        frontend_base_url: str,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender
        self._token_service = token_service
        self._password_reset_expire_minutes = password_reset_expire_minutes
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: RequestPasswordResetInput) -> None:
        user = await self._user_repo.find_by_email(input.email)
        # Always return silently to prevent email enumeration.
        if not user or not user.is_active:
            logger.debug("Password reset requested for unknown/inactive email (not disclosed)")
            return

        logger.info("Password reset requested for user %s", user.id)
        await issue_password_setup_link(
            user,
            purpose="reset",
            expire_minutes=self._password_reset_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
            token_service=self._token_service,
            frontend_base_url=self._frontend_base_url,
        )
