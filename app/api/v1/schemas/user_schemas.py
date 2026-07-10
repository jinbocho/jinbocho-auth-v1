from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole


class UserResponse(BaseModel):
    """User information response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID")
    library_id: UUID = Field(description="Library the user belongs to")
    email: EmailStr = Field(description="User email")
    full_name: str = Field(description="User full name")
    role: UserRole = Field(description="User role")
    is_active: bool = Field(description="Whether the user is active")
    annual_reading_goal: int | None = Field(default=None, description="Annual books-read target (null = no goal set)")
    language: Language | None = Field(default=None, description="UI language preference")
    theme_name: ThemeName | None = Field(default=None, description="UI theme")
    theme_mode: ThemeMode | None = Field(default=None, description="UI colour mode")
    avatar_url: str | None = Field(default=None, description="Profile picture as a data URL (base64 webp, 200×200)")
    password_set_at: datetime | None = Field(
        default=None, description="When the user set their own password; null means their invite is still pending"
    )
    tour_completed_at: datetime | None = Field(
        default=None, description="When the user completed the onboarding tour; null means it hasn't been shown yet"
    )


class UserCreate(BaseModel):
    """Request body to invite a new user. No password is set here — the
    invitee receives an email with a link to choose their own."""
    email: EmailStr = Field(description="User email")
    full_name: str = Field(min_length=1, max_length=255, description="User full name")
    role: UserRole = Field(description="User role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "jane@example.com",
                "full_name": "Jane Smith",
                "role": "editor"
            }
        }
    )


class UserUpdate(BaseModel):
    """Request body to update user information (admin only)."""
    full_name: str | None = Field(default=None, description="New full name")
    role: UserRole | None = Field(default=None, description="New role")
    is_active: bool | None = Field(default=None, description="Active status")
    annual_reading_goal: int | None = Field(default=None, description="Annual reading goal (null = no goal)")
    language: Language | None = Field(default=None, description="UI language preference")
    theme_name: ThemeName | None = Field(default=None, description="UI theme")
    theme_mode: ThemeMode | None = Field(default=None, description="UI colour mode")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Doe",
                "role": "admin",
                "is_active": True,
                "annual_reading_goal": 24,
                "language": "it"
            }
        }
    )


class MeUpdate(BaseModel):
    """Request body for self-update (any authenticated user). Email is
    deliberately absent here — changing it goes through the verify-before-
    apply flow in EmailChangeRequest/EmailChangeConfirm instead, so a typo'd
    or unreachable new address can never lock the account out silently."""
    full_name: str | None = Field(default=None, description="New full name")
    annual_reading_goal: int | None = Field(default=None, description="Annual reading goal (null = no goal)")
    language: Language | None = Field(default=None, description="UI language preference")
    theme_name: ThemeName | None = Field(default=None, description="UI theme")
    theme_mode: ThemeMode | None = Field(default=None, description="UI colour mode")


class EmailChangeRequest(BaseModel):
    """Request body to start a verified email change for the current user."""
    new_email: EmailStr = Field(description="The new email address to verify and switch to")

    model_config = ConfigDict(
        json_schema_extra={"example": {"new_email": "jane.new@example.com"}}
    )
