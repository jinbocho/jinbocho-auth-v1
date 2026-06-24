from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    family_id: UUID
    email: str
    password_hash: str
    full_name: str
    role: str
    is_active: bool = True
    annual_reading_goal: int | None = None
    language: str | None = None
    theme_name: str | None = None
    theme_mode: str | None = None
    # None until the invitee (or the admin who created them) sets a real
    # password via the invite/reset link — the signal used to show "invite
    # pending" in the UI, since is_active is true from creation onward.
    password_set_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
