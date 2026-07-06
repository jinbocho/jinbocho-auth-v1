from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import (
    ConfirmationMismatchError,
    EntityNotFoundError,
    ForbiddenError,
    IncorrectPasswordError,
)
from app.domain.repositories import LibraryRepository, UserRepository
from app.domain.services import PasswordHasher


@dataclass
class VerifyLibraryDeletionInput:
    library_id: UUID
    requester_id: UUID
    requester_library_id: UUID
    password: str
    confirm_library_name: str


class LibraryDeletionVerifier:
    """Password + library-name check shared by the FE's preflight confirmation
    call and the actual delete below — the delete enforces it again itself
    rather than trusting that the preflight call happened first, so a stolen
    JWT alone is never enough to wipe the account."""

    def __init__(
        self,
        library_repo: LibraryRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._library_repo = library_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher

    async def verify(self, input: VerifyLibraryDeletionInput) -> None:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot delete another library")
        library = await self._library_repo.find_by_id(input.library_id)
        if not library:
            raise EntityNotFoundError("Library not found")
        if input.confirm_library_name != library.name:
            raise ConfirmationMismatchError("Library name does not match")
        user = await self._user_repo.find_by_id(input.requester_id)
        if not user or not self._password_hasher.verify(input.password, user.password_hash):
            raise IncorrectPasswordError("Incorrect password")


class ConfirmLibraryDeletionUseCase:
    """Non-destructive preflight check — lets the frontend fail fast on a
    wrong password/name before it wipes the catalog-service library data,
    which must happen before the actual library delete below (see
    DeleteLibraryUseCase's docstring)."""

    def __init__(
        self,
        library_repo: LibraryRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._verifier = LibraryDeletionVerifier(library_repo, user_repo, password_hasher)

    async def execute(self, input: VerifyLibraryDeletionInput) -> None:
        await self._verifier.verify(input)


@dataclass
class DeleteLibraryInput:
    library_id: UUID
    requester_id: UUID
    requester_library_id: UUID
    password: str
    confirm_library_name: str


class DeleteLibraryUseCase:
    """Permanently deletes the library and, via DB cascade, every one of its
    users, refresh tokens and password-reset tokens. Irreversible.

    The catalog-service library data lives in a different database with no
    FK back to this one, so it can't cascade from here — the caller (the
    frontend) must wipe it separately, and should do so *before* this call:
    if the catalog wipe fails, the library/users still exist and the account
    can retry; if this call ran first and then the catalog wipe failed, the
    library would be gone but its library data would be permanently orphaned
    with no account left that could ever reach or clean it up.
    """

    def __init__(
        self,
        library_repo: LibraryRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._library_repo = library_repo
        self._verifier = LibraryDeletionVerifier(library_repo, user_repo, password_hasher)

    async def execute(self, input: DeleteLibraryInput) -> None:
        await self._verifier.verify(
            VerifyLibraryDeletionInput(
                library_id=input.library_id,
                requester_id=input.requester_id,
                requester_library_id=input.requester_library_id,
                password=input.password,
                confirm_library_name=input.confirm_library_name,
            )
        )
        await self._library_repo.delete(input.library_id)
