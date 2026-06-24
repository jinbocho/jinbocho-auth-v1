"""Semantic exceptions raised by use cases and domain services.

Each subclasses one of the builtin exception families already mandated by
the project (LookupError / PermissionError / ValueError) so existing
`pytest.raises(LookupError)`-style assertions keep working, while still
letting `app/core/exception_handlers.py` map each concrete case to its own
HTTP status code instead of collapsing everything to one status per family.
"""


class EntityNotFoundError(LookupError):
    """A requested resource does not exist, or is invisible to the requester."""


class InvalidCredentialsError(LookupError):
    """Authentication failed: unknown email/password pair, or unknown/expired refresh token."""


class InactiveUserError(PermissionError):
    """The authenticated user's account has been deactivated."""


class ForbiddenError(PermissionError):
    """The authenticated user is not allowed to act on this specific resource."""


class IncorrectPasswordError(PermissionError):
    """A re-authentication check (e.g. before a destructive action) failed."""


class ConfirmationMismatchError(ValueError):
    """A typed confirmation value (e.g. the family name) did not match."""


class EmailAlreadyRegisteredError(ValueError):
    """An email address is already associated with an existing account."""


class LastAdminError(ValueError):
    """Refused: this would leave the family with no active admin."""


class InvalidResetTokenError(ValueError):
    """A password-reset/invite token is unknown, expired, or otherwise unusable."""


class ResetTokenAlreadyUsedError(InvalidResetTokenError):
    """A password-reset/invite token has already been consumed."""
