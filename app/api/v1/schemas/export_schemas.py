from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class FamilyExportItem(BaseModel):
    """Family identity, exported for display only (never overwritten on import)."""
    id: UUID
    name: str
    description: Optional[str] = None


class UserExportItem(BaseModel):
    """A family member, exported without any credential. On import, users are
    matched by email (matched, not re-created) or invited exactly like the
    normal 'invite user' flow (they set their own password via email)."""
    id: UUID = Field(description="Original user ID — used to remap references in the catalog import")
    email: EmailStr
    full_name: str
    role: str = Field(pattern="^(admin|editor|viewer)$")
    is_active: bool = True
    annual_reading_goal: Optional[int] = None
    language: Optional[str] = Field(default=None, pattern="^(en|it|es|fr)$")
    theme_name: Optional[str] = Field(default=None, pattern="^(pergamena|akabeni|sumi)$")
    theme_mode: Optional[str] = Field(default=None, pattern="^(light|dark|system)$")


class FamilyDataExportResponse(BaseModel):
    schema_version: int = 1
    family: FamilyExportItem
    users: list[UserExportItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schema_version": 1,
                "family": {"id": "...", "name": "The Smiths", "description": None},
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
