import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.application.ports import EmailService
from app.domain.entities import Library, LibraryMembership, MembershipStatus, User, UserRole
from app.domain.repositories import LibraryRepository, MembershipRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class RegisterLibraryInput:
    library_name: str
    admin_email: str
    admin_password: str
    admin_full_name: str
    # Required, not optional: GDPR Art. 7 requires being able to demonstrate
    # consent was given, so registration must record which policy version the
    # admin actually accepted rather than assuming the "current" one applied.
    accepted_privacy_version: str
    accepted_terms_version: str


@dataclass
class RegisterLibraryOutput:
    library_id: UUID
    user_id: UUID


class RegisterLibraryUseCase:
    def __init__(
        self,
        library_repo: LibraryRepository,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        password_hasher: PasswordHasher,
        email_sender: EmailService,
        frontend_base_url: str,
    ):
        self._library_repo = library_repo
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._password_hasher = password_hasher
        self._email_sender = email_sender
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: RegisterLibraryInput) -> RegisterLibraryOutput:
        if not input.accepted_privacy_version.strip() or not input.accepted_terms_version.strip():
            raise ValueError("Privacy policy and terms of service must be accepted to register")

        library = Library(name=input.library_name)
        library = await self._library_repo.save(library)

        now = datetime.now(timezone.utc)
        user = User(
            library_id=library.id,
            email=input.admin_email,
            password_hash=self._password_hasher.hash(input.admin_password),
            full_name=input.admin_full_name,
            role=UserRole.ADMIN,
            consent_privacy_version=input.accepted_privacy_version,
            consent_terms_version=input.accepted_terms_version,
            consent_at=now,
            last_selected_library_id=library.id,
        )
        user = await self._user_repo.save(user)

        membership = LibraryMembership(
            user_id=user.id,
            library_id=library.id,
            role=UserRole.ADMIN,
            status=MembershipStatus.ACTIVE,
            joined_at=now,
        )
        await self._membership_repo.save(membership)

        await asyncio.to_thread(
            self._email_sender.send_welcome_email,
            user.email,
            library.name,
            f"{self._frontend_base_url}/login",
            language=user.language.value if user.language else None,
        )

        logger.info("Library %s registered with admin %s", library.id, user.id)
        return RegisterLibraryOutput(library_id=library.id, user_id=user.id)
