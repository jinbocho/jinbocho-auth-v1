import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.config import settings
from app.domain.entities import Family, User
from app.domain.repositories import FamilyRepository, UserRepository
from app.domain.services import PasswordHasher
from app.infrastructure.email.email_sender import EmailSender


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
        email_sender: EmailSender,
    ):
        self._family_repo = family_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._email_sender = email_sender

    async def execute(self, input: RegisterFamilyInput) -> RegisterFamilyOutput:
        family = Family(name=input.family_name)
        family = await self._family_repo.save(family)

        user = User(
            family_id=family.id,
            email=input.admin_email,
            password_hash=self._password_hasher.hash(input.admin_password),
            full_name=input.admin_full_name,
            role="admin",
        )
        user = await self._user_repo.save(user)

        await asyncio.to_thread(
            self._email_sender.send_welcome_email,
            user.email,
            family.name,
            f"{settings.frontend_base_url}/login",
            language=user.language,
        )

        return RegisterFamilyOutput(family_id=family.id, user_id=user.id)
