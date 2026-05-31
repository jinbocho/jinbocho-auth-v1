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


class UserCreate(BaseModel):
    """Request body to create a new user."""
    email: EmailStr = Field(description="User email")
    password: str = Field(min_length=8, description="User password (min 8 chars)")
    full_name: str = Field(min_length=1, max_length=255, description="User full name")
    role: str = Field(pattern="^(admin|editor|viewer)$", description="User role: admin, editor, or viewer")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "jane@example.com",
                "password": "SecurePass123!",
                "full_name": "Jane Smith",
                "role": "editor"
            }
        }
    )


class UserUpdate(BaseModel):
    """Request body to update user information."""
    full_name: str | None = Field(default=None, description="New full name")
    role: str | None = Field(default=None, pattern="^(admin|editor|viewer)$", description="New role")
    is_active: bool | None = Field(default=None, description="Active status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Doe",
                "role": "admin",
                "is_active": True
            }
        }
    )
