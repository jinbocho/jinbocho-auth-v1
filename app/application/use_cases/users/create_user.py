from dataclasses import dataclass
from uuid import UUID

from app.application.use_cases.auth.login import pwd_context
from app.domain.entities import User
from app.domain.repositories import UserRepository


@dataclass
class CreateUserInput:
    family_id: UUID
    email: str
    password: str
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
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        existing = await self._user_repo.find_by_email(input.email)
        if existing:
            raise ValueError("Email already registered")

        user = User(
            family_id=input.family_id,
            email=input.email,
            password_hash=pwd_context.hash(input.password),
            full_name=input.full_name,
            role=input.role,
        )
        saved_user = await self._user_repo.save(user)
        return CreateUserOutput(
            id=saved_user.id,
            family_id=saved_user.family_id,
            email=saved_user.email,
            full_name=saved_user.full_name,
            role=saved_user.role,
            is_active=saved_user.is_active,
        )
