from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories import LibraryRepository, UserRepository


@dataclass
class ExportLibraryDataInput:
    library_id: UUID


@dataclass
class UserExportData:
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    annual_reading_goal: int | None = None
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None
    avatar_url: str | None = None
    password_set_at: datetime | None = None
    consent_privacy_version: str | None = None
    consent_terms_version: str | None = None
    consent_at: datetime | None = None


@dataclass
class ExportLibraryDataOutput:
    library_id: UUID
    library_name: str
    library_description: str | None
    library_created_at: datetime
    library_updated_at: datetime
    users: list[UserExportData]


class ExportLibraryDataUseCase:
    """Exports the library's identity and roster for a full backup and for the
    GDPR Art. 15/20 "download my data" bundle. Deliberately excludes
    password_hash: a restored user sets a fresh password through the same
    invite-by-email flow used for inviting a new member (see ImportUsersUseCase).

    Every other personal field on User/Library is included — this is the
    single place a field could be silently missed from an access/portability
    request, so any new PII field added to those entities must be added here too."""

    def __init__(self, library_repo: LibraryRepository, user_repo: UserRepository):
        self._library_repo = library_repo
        self._user_repo = user_repo

    async def execute(self, input: ExportLibraryDataInput) -> ExportLibraryDataOutput:
        library = await self._library_repo.find_by_id(input.library_id)
        if not library:
            raise EntityNotFoundError("Library not found")

        users = await self._user_repo.find_by_library(input.library_id)

        return ExportLibraryDataOutput(
            library_id=library.id,
            library_name=library.name,
            library_description=library.description,
            library_created_at=library.created_at,
            library_updated_at=library.updated_at,
            users=[
                UserExportData(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=UserRole(user.role),
                    is_active=user.is_active,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    annual_reading_goal=user.annual_reading_goal,
                    language=Language(user.language) if user.language else None,
                    theme_name=ThemeName(user.theme_name) if user.theme_name else None,
                    theme_mode=ThemeMode(user.theme_mode) if user.theme_mode else None,
                    avatar_url=user.avatar_url,
                    password_set_at=user.password_set_at,
                    consent_privacy_version=user.consent_privacy_version,
                    consent_terms_version=user.consent_terms_version,
                    consent_at=user.consent_at,
                )
                for user in users
            ],
        )
