from dataclasses import dataclass
from uuid import UUID

from passlib.context import CryptContext

from app.domain.entities import Family, User
from app.domain.repositories import FamilyRepository, UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    def __init__(self, family_repo: FamilyRepository, user_repo: UserRepository):
        self._family_repo = family_repo
        self._user_repo = user_repo

    async def execute(self, input: RegisterFamilyInput) -> RegisterFamilyOutput:
        family = Family(name=input.family_name)
        family = await self._family_repo.save(family)

        user = User(
            family_id=family.id,
            email=input.admin_email,
            password_hash=pwd_context.hash(input.admin_password),
            full_name=input.admin_full_name,
            role="admin",
        )
        user = await self._user_repo.save(user)

        return RegisterFamilyOutput(family_id=family.id, user_id=user.id)
