import secrets
from dataclasses import dataclass
from uuid import UUID

from app.application.services import issue_password_setup_link
from app.application.use_cases.auth.login import pwd_context
from app.config import settings
from app.domain.entities import User
from app.domain.repositories import PasswordResetTokenRepository, UserRepository
from app.infrastructure.email.email_sender import EmailSender


@dataclass
class CreateUserInput:
    family_id: UUID
    email: str
    full_name: str
    role: str


@dataclass
class CreateUserOutput:
    id: UUID
    family_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class CreateUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailSender,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        existing = await self._user_repo.find_by_email(input.email)
        if existing:
            raise ValueError("Email already registered")

        # No password is chosen for the invitee: a random, never-disclosed
        # hash is stored as a placeholder (unusable until they set their own
        # via the invite link) instead of an admin-picked password.
        user = User(
            family_id=input.family_id,
            email=input.email,
            password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
            full_name=input.full_name,
            role=input.role,
        )
        saved_user = await self._user_repo.save(user)

        await issue_password_setup_link(
            saved_user,
            purpose="invite",
            expire_minutes=settings.invite_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
        )

        return CreateUserOutput(
            id=saved_user.id,
            family_id=saved_user.family_id,
            email=saved_user.email,
            full_name=saved_user.full_name,
            role=saved_user.role,
            is_active=saved_user.is_active,
        )
