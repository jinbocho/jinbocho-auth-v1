from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.application.services import TokenService, issue_password_setup_link
from app.config import settings
from app.domain.exceptions import EntityNotFoundError, InvalidResetTokenError
from app.domain.repositories import PasswordResetTokenRepository, UserRepository
from app.infrastructure.email.email_sender import EmailSender


@dataclass
class ResendInviteInput:
    user_id: UUID
    requester_family_id: UUID


class ResendInviteUseCase:
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

    async def execute(self, input: ResendInviteInput) -> None:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or user.family_id != input.requester_family_id:
            raise EntityNotFoundError("User not found")

        if user.password_set_at is not None:
            raise InvalidResetTokenError("User has already set their password")

        await self._reset_token_repo.invalidate_pending(
            user.id, purpose="invite", used_at=datetime.now(timezone.utc)
        )

        await issue_password_setup_link(
            user,
            purpose="invite",
            expire_minutes=settings.invite_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
            token_service=self._token_service,
            frontend_base_url=settings.frontend_base_url,
        )
