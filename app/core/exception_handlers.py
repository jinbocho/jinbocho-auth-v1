"""Global exception handlers for the application.

Use cases raise semantic exceptions (see app/domain/exceptions.py) instead of
FastAPI's HTTPException, so the application/domain layers stay free of any
HTTP knowledge. This module is the single place that maps those exceptions
to HTTP responses — endpoints just call a use case and return its result.
"""

from collections.abc import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.domain.exceptions import (
    ConfirmationMismatchError,
    EmailAlreadyRegisteredError,
    EntityNotFoundError,
    ForbiddenError,
    InactiveUserError,
    IncorrectPasswordError,
    InvalidCredentialsError,
    InvalidEmailChangeTokenError,
    InvalidResetTokenError,
    LastAdminError,
    NotAMemberError,
)


def _make_handler(
    status_code: int, *, www_authenticate: bool = False, detail: str | None = None
) -> Callable[[Request, Exception], JSONResponse]:
    def handler(request: Request, exc: Exception) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if www_authenticate else None
        return JSONResponse(status_code=status_code, content={"detail": detail or str(exc)}, headers=headers)

    return handler


def _handle_integrity_error(request: Request, exc: Exception) -> JSONResponse:
    msg = str(exc).lower()
    if "unique" in msg and "email" in msg:
        detail = "Email already registered"
    else:
        detail = "Database constraint violation"
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": detail})


def configure_exception_handlers(app: FastAPI) -> None:
    """Register one handler per domain exception. Every concrete exception
    raised by the domain/application layer must appear here explicitly —
    broad built-in base-class handlers (LookupError, ValueError, …) are
    intentionally avoided because they catch unrelated infrastructure errors
    (e.g. jinja2.TemplateNotFound is a LookupError subclass and would
    incorrectly produce HTTP 404 for a missing email template)."""
    # slowapi's handler is typed for RateLimitExceeded specifically, which mypy
    # treats as incompatible with the broader Callable[[Request, Exception], ...]
    # that add_exception_handler expects (parameter contravariance).
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_exception_handler(
        InvalidCredentialsError, _make_handler(status.HTTP_401_UNAUTHORIZED, www_authenticate=True)
    )
    app.add_exception_handler(IncorrectPasswordError, _make_handler(status.HTTP_401_UNAUTHORIZED))
    app.add_exception_handler(InactiveUserError, _make_handler(status.HTTP_403_FORBIDDEN))
    app.add_exception_handler(ForbiddenError, _make_handler(status.HTTP_403_FORBIDDEN))
    app.add_exception_handler(NotAMemberError, _make_handler(status.HTTP_403_FORBIDDEN))
    app.add_exception_handler(EntityNotFoundError, _make_handler(status.HTTP_404_NOT_FOUND))
    app.add_exception_handler(ConfirmationMismatchError, _make_handler(status.HTTP_400_BAD_REQUEST))
    app.add_exception_handler(InvalidResetTokenError, _make_handler(status.HTTP_400_BAD_REQUEST))
    app.add_exception_handler(InvalidEmailChangeTokenError, _make_handler(status.HTTP_400_BAD_REQUEST))
    app.add_exception_handler(EmailAlreadyRegisteredError, _make_handler(status.HTTP_409_CONFLICT))
    app.add_exception_handler(LastAdminError, _make_handler(status.HTTP_409_CONFLICT))
    # RegisterLibraryUseCase relies on the DB's unique constraint on email
    # instead of a pre-check, so the conflict surfaces as an IntegrityError.
    app.add_exception_handler(IntegrityError, _handle_integrity_error)
