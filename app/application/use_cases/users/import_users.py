from dataclasses import dataclass, field
from uuid import UUID

from app.application.use_cases.users.create_user import CreateUserInput, CreateUserUseCase
from app.application.use_cases.users.update_user import UpdateUserInput, UpdateUserUseCase
from app.domain.repositories import UserRepository


@dataclass
class ImportUserItem:
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool = True
    annual_reading_goal: int | None = None
    language: str | None = None
    theme_name: str | None = None
    theme_mode: str | None = None


@dataclass
class ImportUsersInput:
    family_id: UUID
    users: list[ImportUserItem] = field(default_factory=list)


@dataclass
class ImportUsersOutput:
    user_id_map: dict[UUID, UUID]
    created: int
    matched: int


class ImportUsersUseCase:
    """Restores a family roster from a backup export.

    Users are matched by email (globally unique across the whole service)
    rather than re-created blindly: a member who already exists — in the
    target family, or because they re-registered before importing — is
    reused as-is, so importing never overwrites their current role/settings
    or sends a spurious invite. Anyone not found is invited exactly like
    CreateUserUseCase already does (placeholder password + email link), then
    the imported role/goal/language/theme/active-state is applied on top —
    the base invite flow only takes email/full_name/role.

    `users` may include entries recovered from catalog-service's removed-
    member snapshots (a former member's real name/email/role, captured at
    the moment they were deleted) — those go through this exact same path,
    so they get a genuine invite under their real email rather than a
    synthetic placeholder. Any owner_id/etc. reference with no snapshot and
    no roster entry is simply left unresolved by the caller; this use case
    never invents an account for it.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        create_user: CreateUserUseCase,
        update_user: UpdateUserUseCase,
    ):
        self._user_repo = user_repo
        self._create_user = create_user
        self._update_user = update_user

    async def execute(self, input: ImportUsersInput) -> ImportUsersOutput:
        user_id_map: dict[UUID, UUID] = {}
        created = 0
        matched = 0

        for item in input.users:
            existing = await self._user_repo.find_by_email(item.email)
            if existing:
                user_id_map[item.id] = existing.id
                matched += 1
                continue

            new_user = await self._create_user.execute(
                CreateUserInput(
                    family_id=input.family_id,
                    email=item.email,
                    full_name=item.full_name,
                    role=item.role,
                )
            )
            await self._update_user.execute(
                UpdateUserInput(
                    user_id=new_user.id,
                    requester_family_id=input.family_id,
                    is_active=item.is_active,
                    annual_reading_goal=item.annual_reading_goal,
                    set_annual_reading_goal=True,
                    language=item.language,
                    theme_name=item.theme_name,
                    theme_mode=item.theme_mode,
                )
            )
            user_id_map[item.id] = new_user.id
            created += 1

        return ImportUsersOutput(user_id_map=user_id_map, created=created, matched=matched)
