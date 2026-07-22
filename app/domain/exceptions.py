"""Semantic exceptions raised by use cases and domain services.

Each subclasses one of the builtin exception libraries already mandated by
the project (LookupError / PermissionError / ValueError) so existing
`pytest.raises(LookupError)`-style assertions keep working, while still
letting `app/core/exception_handlers.py` map each concrete case to its own
HTTP status code instead of collapsing everything to one status per library.
"""


class EntityNotFoundError(LookupError):
    """A requested resource does not exist, or is invisible to the requester."""


class InvalidCredentialsError(LookupError):
    """Authentication failed: unknown email/password pair, or unknown/expired refresh token."""


class InactiveUserError(PermissionError):
    """The authenticated user's account has been deactivated."""


class ForbiddenError(PermissionError):
    """The authenticated user is not allowed to act on this specific resource."""


class NotAMemberError(PermissionError):
    """The authenticated user has no active membership in the target library —
    covers both "never invited" and "invited/suspended/revoked" states, since
    the caller must not learn which one it is (would leak membership existence)."""


class IncorrectPasswordError(PermissionError):
    """A re-authentication check (e.g. before a destructive action) failed."""


class ConfirmationMismatchError(ValueError):
    """A typed confirmation value (e.g. the library name) did not match."""


class EmailAlreadyRegisteredError(ValueError):
    """An email address is already associated with an existing account."""


class LastAdminError(ValueError):
    """Refused: this would leave the library with no active admin."""


class InvalidResetTokenError(ValueError):
    """A password-reset/invite token is unknown, expired, or otherwise unusable."""


class ResetTokenAlreadyUsedError(InvalidResetTokenError):
    """A password-reset/invite token has already been consumed."""


class InvalidEmailChangeTokenError(ValueError):
    """An email-change verification token is unknown, expired, or otherwise unusable."""


class EmailChangeTokenAlreadyUsedError(InvalidEmailChangeTokenError):
    """An email-change verification token has already been consumed."""


class InvalidImageUploadError(ValueError):
    """An uploaded avatar is the wrong content type, too large, or not a
    decodable image at all (including corrupted/malicious files that fail
    PIL's own decode step)."""


class ValidationError(ValueError):
    """Input satisfies its Pydantic schema (right type) but fails a
    use-case-level semantic check the schema can't express — e.g. a free-form
    `status: str` field holding a value outside the allowed transitions, or a
    required consent field submitted empty."""
