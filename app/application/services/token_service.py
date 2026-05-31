from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

import jwt

from app.config import Settings
from app.domain.entities import RefreshToken


class TokenService:
    """Manages JWT access tokens and refresh token lifecycle."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def create_access_token(self, user_id: str, email: str, family_id: str, role: str) -> str:
        """Create a signed JWT access token."""
        payload = {
            "sub": user_id,
            "email": email,
            "family_id": family_id,
            "role": role,
        }
        now = self.utcnow()
        payload["iat"] = now
        payload["exp"] = now + timedelta(minutes=self._settings.access_token_expire_minutes)
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
            raise LookupError("Token expired")
        if token.revoked_at is not None:
            raise LookupError("Token revoked")

    @staticmethod
    def utcnow() -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)
