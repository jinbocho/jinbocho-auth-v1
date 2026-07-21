import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import LibraryMembership, MembershipStatus, User, UserRole
from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.repositories import LibraryRepository, MembershipRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)

# Never resolves — deliberately non-deliverable. A child's login is a real
# email+password pair through the ordinary /login endpoint, but the address
# itself is generated, not a contact point (see the plan's decision 2: this
# was chosen over a from-scratch username+PIN auth path on security grounds).
# ".local"/".invalid"/".test" are rejected outright by pydantic's EmailStr
# (they're RFC 6761 special-use TLDs) — ".internal" passes syntax validation
# while still clearly signalling "not a real internet address".
_KIDS_EMAIL_DOMAIN = "kids.jinbocho.internal"
_MAX_GENERATION_ATTEMPTS = 5


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "child"


@dataclass
class CreateChildAccountInput:
    library_id: UUID
    requester_library_id: UUID
    created_by: UUID
    guardian_email: str
    full_name: str
    password: str
    birth_year: int | None = None


@dataclass
class CreateChildAccountOutput:
    user_id: UUID
    membership_id: UUID
    full_name: str
    # System-generated, non-deliverable — returned so the parent can save/
    # share it with the child as their login identifier.
    email: str


class CreateChildAccountUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        library_repo: LibraryRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._library_repo = library_repo
        self._password_hasher = password_hasher

    async def execute(self, input: CreateChildAccountInput) -> CreateChildAccountOutput:
        if input.library_id != input.requester_library_id:
            raise ForbiddenError("Cannot create a child account in another library")

        library = await self._library_repo.find_by_id(input.library_id)
        if not library:
            raise EntityNotFoundError("Library not found")
        if not library.kids_mode_enabled:
            raise ForbiddenError("Kids mode is not enabled for this library")

        email = await self._generate_unique_email(input.full_name)
        now = datetime.now(timezone.utc)

        user = User(
            library_id=input.library_id,
            email=email,
            password_hash=self._password_hasher.hash(input.password),
            full_name=input.full_name,
            role=UserRole.CHILD,
            guardian_email=input.guardian_email,
            password_set_at=now,
            last_selected_library_id=input.library_id,
            birth_year=input.birth_year,
        )
        saved_user = await self._user_repo.save(user)

        membership = LibraryMembership(
            user_id=saved_user.id,
            library_id=input.library_id,
            role=UserRole.CHILD,
            status=MembershipStatus.ACTIVE,
            invited_by=input.created_by,
            invited_at=now,
            joined_at=now,
        )
        saved_membership = await self._membership_repo.save(membership)

        logger.info("Child account %s created in library %s by %s", saved_user.id, input.library_id, input.created_by)
        return CreateChildAccountOutput(
            user_id=saved_user.id,
            membership_id=saved_membership.id,
            full_name=saved_user.full_name,
            email=saved_user.email,
        )

    async def _generate_unique_email(self, full_name: str) -> str:
        slug = _slugify(full_name)
        for _ in range(_MAX_GENERATION_ATTEMPTS):
            candidate = f"{slug}-{secrets.token_hex(3)}@{_KIDS_EMAIL_DOMAIN}"
            if await self._user_repo.find_by_email(candidate) is None:
                return candidate
        raise RuntimeError("Could not generate a unique child account email")
