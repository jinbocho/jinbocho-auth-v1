from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import FamilyRepository, UserRepository


@dataclass
class ExportFamilyDataInput:
    family_id: UUID


@dataclass
class UserExportData:
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    annual_reading_goal: int | None = None
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None


@dataclass
class ExportFamilyDataOutput:
    family_id: UUID
    family_name: str
    family_description: str | None
    users: list[UserExportData]


class ExportFamilyDataUseCase:
    """Exports the family's identity and roster for a full backup. Deliberately
    excludes password_hash: a restored user sets a fresh password through the
    same invite-by-email flow used for inviting a new member (see ImportUsersUseCase)."""

    def __init__(self, family_repo: FamilyRepository, user_repo: UserRepository):
        self._family_repo = family_repo
        self._user_repo = user_repo

    async def execute(self, input: ExportFamilyDataInput) -> ExportFamilyDataOutput:
        family = await self._family_repo.find_by_id(input.family_id)
        if not family:
            raise EntityNotFoundError("Family not found")

        users = await self._user_repo.find_by_family(input.family_id)

        return ExportFamilyDataOutput(
            family_id=family.id,
            family_name=family.name,
            family_description=family.description,
            users=[
                UserExportData(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=UserRole(user.role),
                    is_active=user.is_active,
                    annual_reading_goal=user.annual_reading_goal,
                    language=Language(user.language) if user.language else None,
                    theme_name=ThemeName(user.theme_name) if user.theme_name else None,
                    theme_mode=ThemeMode(user.theme_mode) if user.theme_mode else None,
                )
                for user in users
            ],
        )
