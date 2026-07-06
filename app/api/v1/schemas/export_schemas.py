from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole


class LibraryExportItem(BaseModel):
    """Library identity, exported for display only (never overwritten on import)."""
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserExportItem(BaseModel):
    """A library member. Used both to restore a backup (users are matched by
    email — matched, not re-created — or invited like the normal 'invite
    user' flow) and as the auth-service part of the GDPR Art. 15/20 'download
    my data' bundle — the audit/consent fields below exist for the latter and
    are ignored by the import endpoint, which only reads the roster fields it
    declares in ImportUserItem."""
    id: UUID = Field(description="Original user ID — used to remap references in the catalog import")
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool = True
    annual_reading_goal: Optional[int] = None
    language: Optional[Language] = None
    theme_name: Optional[ThemeName] = None
    theme_mode: Optional[ThemeMode] = None
    avatar_url: Optional[str] = None
    password_set_at: Optional[datetime] = None
    consent_privacy_version: Optional[str] = None
    consent_terms_version: Optional[str] = None
    consent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LibraryDataExportResponse(BaseModel):
    schema_version: int = 1
    library: LibraryExportItem
    users: list[UserExportItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schema_version": 1,
                "library": {"id": "...", "name": "The Smiths", "description": None},
                "users": [
                    {
                        "id": "...",
                        "email": "jane@example.com",
                        "full_name": "Jane Smith",
                        "role": "admin",
                        "is_active": True,
                    }
                ],
            }
        }
    )


class ImportUsersRequest(BaseModel):
    users: list[UserExportItem]


class ImportUsersResponse(BaseModel):
    user_id_map: dict[str, str] = Field(description="Original user ID -> matched-or-newly-created user ID")
    created: int
    matched: int
