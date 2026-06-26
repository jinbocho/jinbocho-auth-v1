import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.application.ports import EmailService
from app.domain.entities import Family, User, UserRole
from app.domain.repositories import FamilyRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class RegisterFamilyInput:
    family_name: str
    admin_email: str
    admin_password: str
    admin_full_name: str


@dataclass
class RegisterFamilyOutput:
    family_id: UUID
    user_id: UUID


class RegisterFamilyUseCase:
    def __init__(
        self,
        family_repo: FamilyRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        email_sender: EmailService,
        frontend_base_url: str,
    ):
        self._family_repo = family_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._email_sender = email_sender
        self._frontend_base_url = frontend_base_url

    async def execute(self, input: RegisterFamilyInput) -> RegisterFamilyOutput:
        family = Family(name=input.family_name)
        family = await self._family_repo.save(family)

        user = User(
            family_id=family.id,
            email=input.admin_email,
            password_hash=self._password_hasher.hash(input.admin_password),
            full_name=input.admin_full_name,
            role=UserRole.ADMIN,
        )
        user = await self._user_repo.save(user)

        await asyncio.to_thread(
            self._email_sender.send_welcome_email,
            user.email,
            family.name,
            f"{self._frontend_base_url}/login",
            language=user.language.value if user.language else None,
        )

        logger.info("Family %s registered with admin %s", family.id, user.id)
        return RegisterFamilyOutput(family_id=family.id, user_id=user.id)
