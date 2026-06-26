from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    JWTPayload,
    get_create_user_use_case,
    get_current_user_payload,
    get_delete_user_use_case,
    get_family_repository,
    get_import_users_use_case,
    get_resend_invite_use_case,
    get_update_user_use_case,
    get_user_repository,
    require_role,
)
from app.api.v1.schemas.export_schemas import (
    FamilyDataExportResponse,
    FamilyExportItem,
    ImportUsersRequest,
    ImportUsersResponse,
    UserExportItem,
)
from app.api.v1.schemas.user_schemas import MeUpdate, UserCreate, UserResponse, UserUpdate
from app.application.use_cases.users import (
    CreateUserInput,
    CreateUserUseCase,
    DeleteUserInput,
    DeleteUserUseCase,
    ExportFamilyDataInput,
    ExportFamilyDataUseCase,
    GetUserInput,
    GetUserUseCase,
    ImportUserItem,
    ImportUsersInput,
    ImportUsersUseCase,
    ListUsersInput,
    ListUsersUseCase,
    ResendInviteInput,
    ResendInviteUseCase,
    UpdateUserInput,
    UpdateUserUseCase,
)
from app.domain.entities import User
from app.domain.repositories import FamilyRepository, UserRepository

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user's information."
)
async def get_me(
    payload: JWTPayload = Depends(get_current_user_payload),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    use_case = GetUserUseCase(user_repo)
    result = await use_case.execute(
        GetUserInput(user_id=UUID(payload["sub"]), requester_family_id=UUID(payload["family_id"]))
    )
    return UserResponse.model_validate(result)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite new user",
    description="Create a new user in the family and email them a link to set their own "
    "password. Requires admin role."
)
async def create_user(
    request: UserCreate,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
) -> UserResponse:
    result = await use_case.execute(
        CreateUserInput(
            family_id=UUID(payload["family_id"]),
            email=request.email,
            full_name=request.full_name,
            role=request.role,
        )
    )
    return UserResponse.model_validate(result)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List family users",
    description="List all users in the family. Any authenticated family member "
    "(the roster is needed to show who is reading which book)."
)
async def list_users(
    payload: JWTPayload = Depends(get_current_user_payload),
    user_repo: UserRepository = Depends(get_user_repository),
) -> list[User]:
    use_case = ListUsersUseCase(user_repo)
    result = await use_case.execute(ListUsersInput(family_id=UUID(payload["family_id"])))
    return result.users


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update own profile. Any authenticated user can update their own name and reading goal."
)
async def update_me(
    request: MeUpdate,
    payload: JWTPayload = Depends(get_current_user_payload),
    use_case: UpdateUserUseCase = Depends(get_update_user_use_case),
) -> UserResponse:
    result = await use_case.execute(
        UpdateUserInput(
            user_id=UUID(payload["sub"]),
            requester_family_id=UUID(payload["family_id"]),
            full_name=request.full_name,
            annual_reading_goal=request.annual_reading_goal,
            set_annual_reading_goal="annual_reading_goal" in request.model_fields_set,
            language=request.language,
            theme_name=request.theme_name,
            theme_mode=request.theme_mode,
        )
    )
    return UserResponse.model_validate(result)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update user information. Requires admin role."
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: UpdateUserUseCase = Depends(get_update_user_use_case),
) -> UserResponse:
    result = await use_case.execute(
        UpdateUserInput(
            user_id=user_id,
            requester_family_id=UUID(payload["family_id"]),
            full_name=request.full_name,
            role=request.role,
            is_active=request.is_active,
            annual_reading_goal=request.annual_reading_goal,
            set_annual_reading_goal="annual_reading_goal" in request.model_fields_set,
            language=request.language,
            theme_name=request.theme_name,
            theme_mode=request.theme_mode,
        )
    )
    return UserResponse.model_validate(result)


@router.post(
    "/{user_id}/resend-invite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Resend invite",
    description="Resend the invite email with a fresh password-setup link, invalidating any "
    "earlier unused invite link. Only valid while the user hasn't set their password yet. "
    "Requires admin role."
)
async def resend_invite(
    user_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: ResendInviteUseCase = Depends(get_resend_invite_use_case),
) -> None:
    await use_case.execute(
        ResendInviteInput(user_id=user_id, requester_family_id=UUID(payload["family_id"]))
    )


@router.get(
    "/export",
    response_model=FamilyDataExportResponse,
    summary="Export family roster",
    description="Export the family's identity and member roster for a full backup. "
    "Never includes password hashes — restored members set a fresh password via the "
    "same invite-by-email flow used for inviting a new member. Requires admin role."
)
async def export_family_data(
    payload: JWTPayload = Depends(require_role("admin")),
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> FamilyDataExportResponse:
    use_case = ExportFamilyDataUseCase(family_repo, user_repo)
    result = await use_case.execute(ExportFamilyDataInput(family_id=UUID(payload["family_id"])))
    return FamilyDataExportResponse(
        family=FamilyExportItem(id=result.family_id, name=result.family_name, description=result.family_description),
        users=[
            UserExportItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                is_active=u.is_active,
                annual_reading_goal=u.annual_reading_goal,
                language=u.language,
                theme_name=u.theme_name,
                theme_mode=u.theme_mode,
            )
            for u in result.users
        ],
    )


@router.post(
    "/import",
    response_model=ImportUsersResponse,
    summary="Restore family roster from a backup",
    description="Restores users from a backup export into the current family. Each user is "
    "matched by email if one already exists (kept as-is, no duplicate invite); otherwise "
    "they're invited exactly like POST /v1/users. Returns the original-id -> "
    "matched-or-created-id map, needed to restore the catalog-service data next. Requires admin role."
)
async def import_users(
    request: ImportUsersRequest,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: ImportUsersUseCase = Depends(get_import_users_use_case),
) -> ImportUsersResponse:
    result = await use_case.execute(
        ImportUsersInput(
            family_id=UUID(payload["family_id"]),
            users=[
                ImportUserItem(
                    id=item.id,
                    email=item.email,
                    full_name=item.full_name,
                    role=item.role,
                    is_active=item.is_active,
                    annual_reading_goal=item.annual_reading_goal,
                    language=item.language,
                    theme_name=item.theme_name,
                    theme_mode=item.theme_mode,
                )
                for item in request.users
            ],
        )
    )
    return ImportUsersResponse(
        user_id_map={str(old): str(new) for old, new in result.user_id_map.items()},
        created=result.created,
        matched=result.matched,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete user from family. Requires admin role."
)
async def delete_user(
    user_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: DeleteUserUseCase = Depends(get_delete_user_use_case),
) -> None:
    await use_case.execute(
        DeleteUserInput(user_id=user_id, requester_family_id=UUID(payload["family_id"]))
    )
