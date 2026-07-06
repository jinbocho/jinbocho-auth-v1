import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.enums import Language, MembershipStatus, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError, LastAdminError
from app.domain.repositories import MembershipRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class UpdateUserInput:
    user_id: UUID
    requester_library_id: UUID
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
    library_id: UUID
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
    """Same membership-based authorization rationale as GetUserUseCase — see
    its docstring. Powers both PATCH /users/me (self) and the legacy admin
    PATCH /users/{id}, now superseded for role/status management by
    UpdateMembershipUseCase (kept here only for full_name/preferences)."""

    def __init__(self, user_repo: UserRepository, membership_repo: MembershipRepository):
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    async def execute(self, input: UpdateUserInput) -> UpdateUserOutput:
        user = await self._user_repo.find_by_id(input.user_id)
        if not user:
            raise EntityNotFoundError("User not found")
        membership = await self._membership_repo.find_by_user_and_library(user.id, input.requester_library_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise EntityNotFoundError("User not found")

        demoting_admin = input.role is not None and input.role != UserRole.ADMIN
        deactivating = input.is_active is False
        if membership.role == UserRole.ADMIN and (demoting_admin or deactivating):
            siblings = await self._membership_repo.find_by_library(input.requester_library_id, [MembershipStatus.ACTIVE])
            other_active_admins = any(s.user_id != user.id and s.role == UserRole.ADMIN for s in siblings)
            if not other_active_admins:
                raise LastAdminError("Cannot remove the library's last active admin")

        if input.full_name is not None:
            user.full_name = input.full_name
        if input.set_annual_reading_goal:
            user.annual_reading_goal = input.annual_reading_goal
        if input.language is not None:
            user.language = input.language
        if input.theme_name is not None:
            user.theme_name = input.theme_name
        if input.theme_mode is not None:
            user.theme_mode = input.theme_mode

        # Role/active-status live on the membership now, not the legacy user
        # scalar — update both so the legacy field never silently disagrees
        # with what's actually enforced (see require_role, which reads the
        # JWT's role claim, itself sourced from the membership at select time).
        if input.role is not None:
            user.role = input.role
            membership.role = input.role
        if input.is_active is not None:
            user.is_active = input.is_active
            membership.status = MembershipStatus.ACTIVE if input.is_active else MembershipStatus.SUSPENDED

        if input.role is not None or input.is_active is not None:
            membership = await self._membership_repo.save(membership)

        updated_user = await self._user_repo.save(user)
        logger.info("User %s updated by library %s", input.user_id, input.requester_library_id)
        return UpdateUserOutput(
            id=updated_user.id,
            library_id=input.requester_library_id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=membership.role,
            is_active=updated_user.is_active,
            annual_reading_goal=updated_user.annual_reading_goal,
            language=updated_user.language,
            theme_name=updated_user.theme_name,
            theme_mode=updated_user.theme_mode,
            avatar_url=updated_user.avatar_url,
            password_set_at=updated_user.password_set_at,
        )
