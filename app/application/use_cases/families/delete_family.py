from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import (
    ConfirmationMismatchError,
    EntityNotFoundError,
    ForbiddenError,
    IncorrectPasswordError,
)
from app.domain.repositories import FamilyRepository, UserRepository
from app.domain.services import PasswordHasher


@dataclass
class VerifyFamilyDeletionInput:
    family_id: UUID
    requester_id: UUID
    requester_family_id: UUID
    password: str
    confirm_family_name: str


class FamilyDeletionVerifier:
    """Password + family-name check shared by the FE's preflight confirmation
    call and the actual delete below — the delete enforces it again itself
    rather than trusting that the preflight call happened first, so a stolen
    JWT alone is never enough to wipe the account."""

    def __init__(
        self,
        family_repo: FamilyRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._family_repo = family_repo
        self._user_repo = user_repo
        self._password_hasher = password_hasher

    async def verify(self, input: VerifyFamilyDeletionInput) -> None:
        if input.family_id != input.requester_family_id:
            raise ForbiddenError("Cannot delete another family")
        family = await self._family_repo.find_by_id(input.family_id)
        if not family:
            raise EntityNotFoundError("Family not found")
        if input.confirm_family_name != family.name:
            raise ConfirmationMismatchError("Family name does not match")
        user = await self._user_repo.find_by_id(input.requester_id)
        if not user or not self._password_hasher.verify(input.password, user.password_hash):
            raise IncorrectPasswordError("Incorrect password")


class ConfirmFamilyDeletionUseCase:
    """Non-destructive preflight check — lets the frontend fail fast on a
    wrong password/name before it wipes the catalog-service library data,
    which must happen before the actual family delete below (see
    DeleteFamilyUseCase's docstring)."""

    def __init__(
        self,
        family_repo: FamilyRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._verifier = FamilyDeletionVerifier(family_repo, user_repo, password_hasher)

    async def execute(self, input: VerifyFamilyDeletionInput) -> None:
        await self._verifier.verify(input)


@dataclass
class DeleteFamilyInput:
    family_id: UUID
    requester_id: UUID
    requester_family_id: UUID
    password: str
    confirm_family_name: str


class DeleteFamilyUseCase:
    """Permanently deletes the family and, via DB cascade, every one of its
    users, refresh tokens and password-reset tokens. Irreversible.

    The catalog-service library data lives in a different database with no
    FK back to this one, so it can't cascade from here — the caller (the
    frontend) must wipe it separately, and should do so *before* this call:
    if the catalog wipe fails, the family/users still exist and the account
    can retry; if this call ran first and then the catalog wipe failed, the
    family would be gone but its library data would be permanently orphaned
    with no account left that could ever reach or clean it up.
    """

    def __init__(
        self,
        family_repo: FamilyRepository,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
    ):
        self._family_repo = family_repo
        self._verifier = FamilyDeletionVerifier(family_repo, user_repo, password_hasher)

    async def execute(self, input: DeleteFamilyInput) -> None:
        await self._verifier.verify(
            VerifyFamilyDeletionInput(
                family_id=input.family_id,
                requester_id=input.requester_id,
                requester_family_id=input.requester_family_id,
                password=input.password,
                confirm_family_name=input.confirm_family_name,
            )
        )
        await self._family_repo.delete(input.family_id)
