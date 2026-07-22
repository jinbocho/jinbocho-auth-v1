import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.application.ports import EmailService
from app.application.services import TokenService, issue_password_setup_link
from app.domain.entities import LibraryMembership, MembershipStatus, User, UserRole
from app.domain.exceptions import EmailAlreadyRegisteredError
from app.domain.repositories import MembershipRepository, PasswordResetTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class CreateUserInput:
    library_id: UUID
    email: str
    full_name: str
    role: UserRole


@dataclass
class CreateUserOutput:
    id: UUID
    library_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    password_set_at: datetime | None = None


class CreateUserUseCase:
    """Legacy single-library invite path — still used internally by
    ImportUsersUseCase to recreate users during a backup restore. Also
    creates the corresponding LibraryMembership row (active, matching the
    legacy scalar) so every user this creates is reachable by the same
    membership-based checks the rest of the app now uses (GetUserUseCase,
    UpdateUserUseCase, etc.) — without it, the UpdateUserInput call that
    ImportUsersUseCase makes right after this would 404."""

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        reset_token_repo: PasswordResetTokenRepository,
        email_sender: EmailService,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        invite_expire_minutes: int,
        frontend_base_url: str,
    ):
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._reset_token_repo = reset_token_repo
        self._email_sender = email_sender
        self._token_service = token_service
        self._password_hasher = password_hasher
        self._invite_expire_minutes = invite_expire_minutes
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        # Normalized once and reused for both the dedup check and storage —
        # otherwise "user@x.com" and "User@x.com" pass the duplicate check as
        # distinct accounts for the same real mailbox (confirmed via pentest).
        email = input.email.strip().lower()
        existing = await self._user_repo.find_by_email(email)
        if existing and existing.is_active:
            raise EmailAlreadyRegisteredError("Email already registered")

        # No password is chosen for the invitee: a random, never-disclosed
        # hash is stored as a placeholder (unusable until they set their own
        # via the invite link) instead of an admin-picked password.
        user = User(
            library_id=input.library_id,
            email=email,
            password_hash=self._password_hasher.hash(secrets.token_urlsafe(32)),
            full_name=input.full_name,
            role=UserRole(input.role),
            last_selected_library_id=input.library_id,
        )
        saved_user = await self._user_repo.save(user)

        now = datetime.now(timezone.utc)
        await self._membership_repo.save(
            LibraryMembership(
                user_id=saved_user.id, library_id=input.library_id, role=UserRole(input.role),
                status=MembershipStatus.ACTIVE, joined_at=now,
            )
        )
        logger.info("User %s invited to library %s with role %s", saved_user.id, input.library_id, input.role)

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
            library_id=saved_user.library_id,
            email=saved_user.email,
            full_name=saved_user.full_name,
            role=saved_user.role,
            is_active=saved_user.is_active,
        )
