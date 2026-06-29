import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class GetUserInput:
    user_id: UUID
    requester_family_id: UUID


@dataclass
class GetUserOutput:
    id: UUID
    family_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    annual_reading_goal: int | None = None
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None
    avatar_url: str | None = None
    password_set_at: datetime | None = None


class GetUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: GetUserInput) -> GetUserOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or user.family_id != input.requester_family_id:
            raise EntityNotFoundError("User not found")

        logger.debug("User %s fetched by family %s", input.user_id, input.requester_family_id)
        return GetUserOutput(
            id=user.id,
            family_id=user.family_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            annual_reading_goal=user.annual_reading_goal,
            language=user.language,
            theme_name=user.theme_name,
            theme_mode=user.theme_mode,
            avatar_url=user.avatar_url,
            password_set_at=user.password_set_at,
        )
