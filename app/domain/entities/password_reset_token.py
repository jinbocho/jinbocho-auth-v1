from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PasswordResetToken:
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    # "reset": user requested a forgotten-password link.
    # "invite": admin created the account; this is its first password setup.
    purpose: str = "reset"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
