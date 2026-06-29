import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError, LastAdminError
from app.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class UpdateUserInput:
    user_id: UUID
    requester_family_id: UUID
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    # For annual_reading_goal: None can mean "no goal" (a valid value) or "not provided".
    # set_annual_reading_goal=True means the caller explicitly wants to apply the value
    # (even if it's None, which clears the goal). False means "leave unchanged".
    annual_reading_goal: int | None = None
    set_annual_reading_goal: bool = False
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None


@dataclass
class UpdateUserOutput:
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


class UpdateUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(self, input: UpdateUserInput) -> UpdateUserOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user or user.family_id != input.requester_family_id:
            raise EntityNotFoundError("User not found")

        demoting_admin = input.role is not None and input.role != UserRole.ADMIN
        deactivating = input.is_active is False
        if user.role == UserRole.ADMIN and user.is_active and (demoting_admin or deactivating):
            family = await self._user_repo.find_by_family(user.family_id)
            other_active_admins = any(
                u.id != user.id and u.role == UserRole.ADMIN and u.is_active for u in family
            )
            if not other_active_admins:
                raise LastAdminError("Cannot remove the family's last active admin")

        if input.full_name is not None:
            user.full_name = input.full_name
        if input.role is not None:
            user.role = input.role
        if input.is_active is not None:
            user.is_active = input.is_active
        if input.set_annual_reading_goal:
            user.annual_reading_goal = input.annual_reading_goal
        if input.language is not None:
            user.language = input.language
        if input.theme_name is not None:
            user.theme_name = input.theme_name
        if input.theme_mode is not None:
            user.theme_mode = input.theme_mode

        updated_user = await self._user_repo.save(user)
        logger.info("User %s updated by family %s", input.user_id, input.requester_family_id)
        return UpdateUserOutput(
            id=updated_user.id,
            family_id=updated_user.family_id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=updated_user.role,
            is_active=updated_user.is_active,
            annual_reading_goal=updated_user.annual_reading_goal,
            language=updated_user.language,
            theme_name=updated_user.theme_name,
            theme_mode=updated_user.theme_mode,
            avatar_url=updated_user.avatar_url,
            password_set_at=updated_user.password_set_at,
        )
