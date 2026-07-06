from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LibrarySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    library_id: UUID = Field(description="Library id")
    name: str = Field(description="Library name")
    role: str = Field(description="Caller's role in this library")
    status: str = Field(description="Membership status: active, invited, or suspended")
    last_accessed_at: datetime | None = Field(default=None, description="Last time this library was the active context")


class SelectLibraryRequest(BaseModel):
    library_id: UUID = Field(description="Library to make the active context")


class ContextTokenResponse(BaseModel):
    """Returned by select/switch — only the access token changes; the
    refresh token (and thus the underlying session) is untouched."""

    access_token: str = Field(description="New JWT access token, scoped to the selected library")
    library_id: UUID = Field(description="The now-active library id")
    role: str = Field(description="Caller's role in the now-active library")
    token_type: str = Field(default="bearer")


class InviteMemberRequest(BaseModel):
    email: EmailStr = Field(description="Email of the person to invite")
    full_name: str | None = Field(default=None, description="Required only if this creates a brand-new account")
    role: str = Field(description="Role to grant: admin, editor, or viewer")


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: str
    status: str
    joined_at: datetime | None = None
    last_accessed_at: datetime | None = None
    avatar_url: str | None = None


class UpdateMembershipRequest(BaseModel):
    role: str | None = Field(default=None, description="New role: admin, editor, or viewer")
    status: str | None = Field(default=None, description="New status: active or suspended")


class MemberSearchResultResponse(BaseModel):
    """Typeahead result for 'lend to a Jinbocho user' — scoped to one
    library's active roster, so role/avatar are fine to expose (the caller
    already sees the full roster via GET .../members)."""

    user_id: UUID
    full_name: str
    email: EmailStr
    role: str
    avatar_url: str | None = None


class GlobalUserSearchResultResponse(BaseModel):
    """Typeahead result for inviting an existing account into a *different*
    library — deliberately minimal (no role, no avatar, no other library
    membership) since this is the one cross-tenant lookup in the system."""

    user_id: UUID
    full_name: str
    email: EmailStr


class MemberProfileResponse(BaseModel):
    """Single member's basic profile — open to any active member (unlike
    MemberResponse's roster, which is admin-only), for viewing a fellow
    member's page (e.g. clicked from a loan's borrower name)."""

    user_id: UUID
    full_name: str
    email: EmailStr
    role: str
    avatar_url: str | None = None
    joined_at: datetime | None = None
