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
