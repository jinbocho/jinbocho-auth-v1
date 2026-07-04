from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.entities.enums import Language, ThemeMode, ThemeName, UserRole


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    family_id: UUID
    email: str
    password_hash: str
    full_name: str
    role: UserRole
    is_active: bool = True
    annual_reading_goal: int | None = None
    language: Language | None = None
    theme_name: ThemeName | None = None
    theme_mode: ThemeMode | None = None
    # None until the invitee (or the admin who created them) sets a real
    # password via the invite/reset link — the signal used to show "invite
    # pending" in the UI, since is_active is true from creation onward.
    avatar_url: str | None = None
    password_set_at: datetime | None = None
    # Set only on the admin who completes registration — GDPR Art. 7 requires
    # being able to demonstrate consent, so the version string accepted and
    # the moment of acceptance are recorded rather than inferred from
    # registration date. None on invited members: their acceptance is implicit
    # in the admin's, since only the admin can register/delete the family.
    consent_privacy_version: str | None = None
    consent_terms_version: str | None = None
    consent_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
