from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for family registration."""
    family_name: str = Field(min_length=1, max_length=255, description="Family name (e.g., 'Smith Family')")
    admin_email: EmailStr = Field(description="Admin user email")
    admin_password: str = Field(min_length=8, description="Admin password (min 8 chars)")
    admin_full_name: str = Field(min_length=1, max_length=255, description="Admin user full name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "family_name": "Smith Family",
                "admin_email": "john@example.com",
                "admin_password": "SecurePass123!",
                "admin_full_name": "John Smith"
            }
        }
    )


class RegisterResponse(BaseModel):
    """Response after successful family registration."""
    family_id: UUID = Field(description="Newly created family ID")
    user_id: UUID = Field(description="Newly created admin user ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "family_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
            }
        }
    )


class LoginRequest(BaseModel):
    """Request body for user login."""
    email: EmailStr = Field(description="User email")
    password: str = Field(description="User password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john@example.com",
                "password": "SecurePass123!"
            }
        }
    )


class TokenResponse(BaseModel):
    """JWT token response containing access and refresh tokens."""
    access_token: str = Field(description="JWT access token (expires in 30 minutes)")
    refresh_token: str = Field(description="Refresh token for obtaining new access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "a1b2c3d4e5f6...",
                "token_type": "bearer"
            }
        }
    )


class RefreshRequest(BaseModel):
    """Request body to refresh access token."""
    refresh_token: str = Field(description="Valid refresh token")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "a1b2c3d4e5f6..."
            }
        }
    )


class LogoutRequest(BaseModel):
    """Request body to logout and revoke refresh token."""
    refresh_token: str = Field(description="Refresh token to revoke")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "a1b2c3d4e5f6..."
            }
        }
    )


class UserSummary(BaseModel):
    """User summary information."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID")
    family_id: UUID = Field(description="Family the user belongs to")
    email: EmailStr = Field(description="User email")
    full_name: str = Field(description="User full name")
    role: str = Field(description="User role: admin, editor, or viewer")
    is_active: bool = Field(description="Whether the user is active")
