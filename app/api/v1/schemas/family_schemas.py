from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FamilyResponse(BaseModel):
    """Family information response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Family ID")
    name: str = Field(description="Family name")
    description: str | None = Field(default=None, description="Optional family description")


class FamilyUpdate(BaseModel):
    """Request body to update family information."""
    name: str | None = Field(default=None, description="New family name")
    description: str | None = Field(default=None, description="New family description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Smith Family",
                "description": "The Smith family library"
            }
        }
    )


class DeleteFamilyRequest(BaseModel):
    """Confirmation payload for the irreversible full-account deletion —
    required by both the preflight check and the actual delete, so a stolen
    JWT alone is never enough to wipe the account."""
    password: str = Field(description="The requesting admin's current password")
    confirm_family_name: str = Field(description="Must exactly match the family's current name")


class RevokeSessionsResponse(BaseModel):
    """Result of an emergency family-wide session revocation."""
    revoked_count: int = Field(description="Number of active refresh tokens revoked across all family members")
