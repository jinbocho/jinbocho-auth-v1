from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.entities.enums import MembershipStatus, UserRole


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LibraryMembership:
    """A user's role and standing within one library (tenant).

    Field is named ``library_id`` — not ``library_id`` — to match the existing
    ``libraries`` table (see ADR-011: the library->library rename is deferred to
    a later, purely-mechanical pass so it doesn't compound with this schema
    change). The entity name uses "Library" since that's the user-facing
    concept this membership represents.
    """

    user_id: UUID
    library_id: UUID
    role: UserRole
    status: MembershipStatus = MembershipStatus.ACTIVE
    invited_by: UUID | None = None
    invited_at: datetime | None = None
    joined_at: datetime | None = None
    last_accessed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
