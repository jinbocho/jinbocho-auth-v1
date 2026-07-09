from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EmailChangeToken:
    user_id: UUID
    # The address being verified — not applied to the user until this token
    # is confirmed, so a typo'd or unreachable new address can never lock
    # the account out silently.
    new_email: str
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
