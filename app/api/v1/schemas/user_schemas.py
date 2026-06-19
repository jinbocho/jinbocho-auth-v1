from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """User information response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID")
    family_id: UUID = Field(description="Family the user belongs to")
    email: EmailStr = Field(description="User email")
    full_name: str = Field(description="User full name")
    role: str = Field(description="User role: admin, editor, or viewer")
    is_active: bool = Field(description="Whether the user is active")
    annual_reading_goal: int | None = Field(default=None, description="Annual books-read target (null = no goal set)")
    language: str | None = Field(default=None, description="UI language preference: en, it, es, fr")
    theme_name: str | None = Field(default=None, description="UI theme: pergamena, akabeni, sumi")
    theme_mode: str | None = Field(default=None, description="UI colour mode: light, dark, system")


class UserCreate(BaseModel):
    """Request body to invite a new user. No password is set here — the
    invitee receives an email with a link to choose their own."""
    email: EmailStr = Field(description="User email")
    full_name: str = Field(min_length=1, max_length=255, description="User full name")
    role: str = Field(pattern="^(admin|editor|viewer)$", description="User role: admin, editor, or viewer")

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
    role: str | None = Field(default=None, pattern="^(admin|editor|viewer)$", description="New role")
    is_active: bool | None = Field(default=None, description="Active status")
    annual_reading_goal: int | None = Field(default=None, description="Annual reading goal (null = no goal)")
    language: str | None = Field(default=None, pattern="^(en|it|es|fr)$", description="UI language preference: en, it, es, fr")
    theme_name: str | None = Field(default=None, pattern="^(pergamena|akabeni|sumi)$", description="UI theme: pergamena, akabeni, sumi")
    theme_mode: str | None = Field(default=None, pattern="^(light|dark|system)$", description="UI colour mode: light, dark, system")

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
    """Request body for self-update (any authenticated user)."""
    full_name: str | None = Field(default=None, description="New full name")
    annual_reading_goal: int | None = Field(default=None, description="Annual reading goal (null = no goal)")
    language: str | None = Field(default=None, pattern="^(en|it|es|fr)$", description="UI language preference: en, it, es, fr")
    theme_name: str | None = Field(default=None, pattern="^(pergamena|akabeni|sumi)$", description="UI theme: pergamena, akabeni, sumi")
    theme_mode: str | None = Field(default=None, pattern="^(light|dark|system)$", description="UI colour mode: light, dark, system")
