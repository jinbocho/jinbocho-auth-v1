from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LibraryResponse(BaseModel):
    """Library information response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Library ID")
    name: str = Field(description="Library name")
    description: str | None = Field(default=None, description="Optional library description")


class LibraryUpdate(BaseModel):
    """Request body to update library information."""
    name: str | None = Field(default=None, description="New library name")
    description: str | None = Field(default=None, description="New library description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Smith Library",
                "description": "The Smith family's home library"
            }
        }
    )


class DeleteLibraryRequest(BaseModel):
    """Confirmation payload for the irreversible full-account deletion —
    required by both the preflight check and the actual delete, so a stolen
    JWT alone is never enough to wipe the account."""
    password: str = Field(description="The requesting admin's current password")
    confirm_library_name: str = Field(description="Must exactly match the library's current name")


class RevokeSessionsResponse(BaseModel):
    """Result of an emergency library-wide session revocation."""
    revoked_count: int = Field(description="Number of active refresh tokens revoked across all library members")
