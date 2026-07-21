from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

import jwt

from app.config import Settings
from app.domain.entities import RefreshToken
from app.domain.exceptions import InvalidCredentialsError


class TokenService:
    """Manages JWT access tokens and refresh token lifecycle."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def create_access_token(
        self,
        user_id: str,
        email: str,
        library_id: str | None,
        role: str | None,
        kids_mode_enabled: bool = False,
        birth_year: int | None = None,
        language: str | None = None,
    ) -> str:
        """Create a signed JWT access token.

        library_id/role are omitted (not merely null) when the user hasn't
        selected an active library yet — a "context-less" token. Such a token
        authenticates the user but authorizes nothing tenant-scoped: catalog
        and ai-service already `require` the library_id claim to be present,
        so a context-less token is rejected by them automatically without any
        change on their side.

        kids_mode_enabled mirrors the target library's flag at issuance time —
        catalog-service's kids-mode use cases re-check it on every request
        (rather than trusting a stale claim indefinitely), so staleness here
        is bounded by the access token's short expiry.

        birth_year (omitted when unset) lets catalog-service derive the
        reader's age band without a cross-service call — see KID-01 in
        jinbocho-docs/backlog/BACKLOG_KIDS_READING_EDUCATION.md. Year only,
        not full date of birth.

        language (omitted when unset) is the user's own UI language
        preference — catalog-service/ai-service read it to generate AI
        content (quiz, discussion questions, incipit, tags) in the reader's
        own language instead of the book's bibliographic language.
        """
        now = self.utcnow()
        payload = {
            "sub": user_id,
            "email": email,
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.access_token_expire_minutes),
            "kids_mode_enabled": kids_mode_enabled,
        }
        if library_id is not None:
            payload["library_id"] = library_id
        if role is not None:
            payload["role"] = role
        if birth_year is not None:
            payload["birth_year"] = birth_year
        if language is not None:
            payload["language"] = language
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def create_refresh_token(self) -> str:
        """Generate a cryptographically secure refresh token."""
        return secrets.token_hex(32)

    def hash_token(self, token: str) -> str:
        """Hash a token for storage (SHA-256)."""
        return sha256(token.encode("utf-8")).hexdigest()

    def validate_token_not_revoked(self, token: RefreshToken, now: datetime) -> None:
        """Validate a refresh token is not expired or revoked."""
        if token.expires_at < now:
            raise InvalidCredentialsError("Token expired")
        if token.revoked_at is not None:
            raise InvalidCredentialsError("Token revoked")

    @property
    def refresh_token_expire_days(self) -> int:
        return self._settings.refresh_token_expire_days

    @staticmethod
    def utcnow() -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)
