import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.ports import EmailService
from app.application.services import TokenService, issue_password_setup_link
from app.domain.entities import User, UserRole
from app.domain.exceptions import EmailAlreadyRegisteredError
from app.domain.repositories import PasswordResetTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class CreateUserInput:
    family_id: UUID
    email: str
    full_name: str
    role: UserRole


@dataclass
class CreateUserOutput:
    id: UUID
    family_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    password_set_at: datetime | None = None


class CreateUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailService,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        invite_expire_minutes: int,
        frontend_base_url: str,
    ):
        self._user_repo = user_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender
        self._token_service = token_service
        self._password_hasher = password_hasher
        self._invite_expire_minutes = invite_expire_minutes
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        existing = await self._user_repo.find_by_email(input.email)
        if existing:
            raise EmailAlreadyRegisteredError("Email already registered")

        # No password is chosen for the invitee: a random, never-disclosed
        # hash is stored as a placeholder (unusable until they set their own
        # via the invite link) instead of an admin-picked password.
        user = User(
            family_id=input.family_id,
            email=input.email,
            password_hash=self._password_hasher.hash(secrets.token_urlsafe(32)),
            full_name=input.full_name,
            role=UserRole(input.role),
        )
        saved_user = await self._user_repo.save(user)
        logger.info("User %s invited to family %s with role %s", saved_user.id, input.family_id, input.role)

        await issue_password_setup_link(
            saved_user,
            purpose="invite",
            expire_minutes=self._invite_expire_minutes,
            reset_token_repo=self._reset_token_repo,
            email_sender=self._email_sender,
            token_service=self._token_service,
            frontend_base_url=self._frontend_base_url,
        )

        return CreateUserOutput(
            id=saved_user.id,
            family_id=saved_user.family_id,
            email=saved_user.email,
            full_name=saved_user.full_name,
            role=saved_user.role,
            is_active=saved_user.is_active,
        )
