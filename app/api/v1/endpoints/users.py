from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.api.dependencies import (
    JWTPayload,
    get_create_user_use_case,
    get_delete_avatar_use_case,
    get_delete_user_use_case,
    get_library_repository,
    get_import_users_use_case,
    get_membership_repository,
    get_resend_invite_use_case,
    get_search_users_use_case,
    get_update_user_use_case,
    get_upload_avatar_use_case,
    get_user_repository,
    require_library_context,
    require_role,
)
from app.api.v1.schemas.context_schemas import GlobalUserSearchResultResponse
from app.api.v1.schemas.export_schemas import (
    LibraryDataExportResponse,
    LibraryExportItem,
    ImportUsersRequest,
    ImportUsersResponse,
    UserExportItem,
)
from app.api.v1.schemas.user_schemas import MeUpdate, UserCreate, UserResponse, UserUpdate
from app.application.use_cases.users import (
    CreateUserInput,
    CreateUserUseCase,
    DeleteAvatarInput,
    DeleteAvatarUseCase,
    DeleteUserInput,
    DeleteUserUseCase,
    ExportLibraryDataInput,
    ExportLibraryDataUseCase,
    GetUserInput,
    GetUserUseCase,
    ImportUserItem,
    ImportUsersInput,
    ImportUsersUseCase,
    ListUsersInput,
    ListUsersUseCase,
    ResendInviteInput,
    ResendInviteUseCase,
    SearchUsersInput,
    SearchUsersUseCase,
    UpdateUserInput,
    UpdateUserUseCase,
    UploadAvatarInput,
    UploadAvatarUseCase,
)
from app.domain.entities import User
from app.domain.repositories import LibraryRepository, MembershipRepository, UserRepository
from app.limiter import limiter

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user's information."
)
async def get_me(
    payload: JWTPayload = Depends(require_library_context),
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UserResponse:
    use_case = GetUserUseCase(user_repo, membership_repo)
    result = await use_case.execute(
        GetUserInput(user_id=UUID(payload["sub"]), requester_library_id=UUID(payload["library_id"]))
    )
    return UserResponse.model_validate(result)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite new user",
    description="Create a new user in the library and email them a link to set their own "
    "password. Requires admin role."
)
async def create_user(
    request: UserCreate,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
) -> UserResponse:
    result = await use_case.execute(
        CreateUserInput(
            library_id=UUID(payload["library_id"]),
            email=request.email,
            full_name=request.full_name,
            role=request.role,
        )
    )
    return UserResponse.model_validate(result)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List library users",
    description="List all users in the library. Any authenticated library member "
    "(the roster is needed to show who is reading which book)."
)
async def list_users(
    payload: JWTPayload = Depends(require_library_context),
    user_repo: UserRepository = Depends(get_user_repository),
) -> list[User]:
    use_case = ListUsersUseCase(user_repo)
    result = await use_case.execute(ListUsersInput(library_id=UUID(payload["library_id"])))
    return result.users


@router.get(
    "/search",
    response_model=list[GlobalUserSearchResultResponse],
    summary="Cross-tenant typeahead search for inviting an existing account",
    description="Searches every Jinbocho account (not just this library's roster) — for "
    "inviting an existing user into a *different* library. The one cross-tenant lookup in "
    "the system: admin-only, rate-limited, requires at least 4 characters, and returns only "
    "name/email (no role, no other library membership). See "
    "jinbocho-docs/architecture/user-search-plan.md for the privacy rationale."
)
@limiter.limit("20/minute")
async def search_users(
    request: Request,
    q: str,
    limit: int = 3,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: SearchUsersUseCase = Depends(get_search_users_use_case),
) -> list[GlobalUserSearchResultResponse]:
    result = await use_case.execute(
        SearchUsersInput(
            query=q,
            exclude_library_id=UUID(payload["library_id"]),
            requested_by=UUID(payload["sub"]),
            limit=min(limit, 10),
        )
    )
    return [
        GlobalUserSearchResultResponse(user_id=r.user_id, full_name=r.full_name, email=r.email)
        for r in result.results
    ]


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update own profile. Any authenticated user can update their own name and reading goal."
)
async def update_me(
    request: MeUpdate,
    payload: JWTPayload = Depends(require_library_context),
    use_case: UpdateUserUseCase = Depends(get_update_user_use_case),
) -> UserResponse:
    result = await use_case.execute(
        UpdateUserInput(
            user_id=UUID(payload["sub"]),
            requester_library_id=UUID(payload["library_id"]),
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
            requester_library_id=UUID(payload["library_id"]),
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
        ResendInviteInput(user_id=user_id, requester_library_id=UUID(payload["library_id"]))
    )


@router.get(
    "/export",
    response_model=LibraryDataExportResponse,
    summary="Export library roster",
    description="Export the library's identity and member roster for a full backup. "
    "Never includes password hashes — restored members set a fresh password via the "
    "same invite-by-email flow used for inviting a new member. Requires admin role."
)
async def export_library_data(
    payload: JWTPayload = Depends(require_role("admin")),
    library_repo: LibraryRepository = Depends(get_library_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> LibraryDataExportResponse:
    use_case = ExportLibraryDataUseCase(library_repo, user_repo)
    result = await use_case.execute(ExportLibraryDataInput(library_id=UUID(payload["library_id"])))
    return LibraryDataExportResponse(
        library=LibraryExportItem(
            id=result.library_id,
            name=result.library_name,
            description=result.library_description,
            created_at=result.library_created_at,
            updated_at=result.library_updated_at,
        ),
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
                avatar_url=u.avatar_url,
                password_set_at=u.password_set_at,
                consent_privacy_version=u.consent_privacy_version,
                consent_terms_version=u.consent_terms_version,
                consent_at=u.consent_at,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
            for u in result.users
        ],
    )


@router.post(
    "/import",
    response_model=ImportUsersResponse,
    summary="Restore library roster from a backup",
    description="Restores users from a backup export into the current library. Each user is "
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
            library_id=UUID(payload["library_id"]),
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


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="Upload profile picture",
    description="Upload a JPEG, PNG, or WebP image as the current user's profile picture. "
    "The image is resized server-side to 200×200 px and stored as a WebP data URL."
)
async def upload_avatar(
    file: UploadFile = File(...),
    payload: JWTPayload = Depends(require_library_context),
    use_case: UploadAvatarUseCase = Depends(get_upload_avatar_use_case),
    user_repo: UserRepository = Depends(get_user_repository),
    membership_repo: MembershipRepository = Depends(get_membership_repository),
) -> UserResponse:
    image_bytes = await file.read()
    await use_case.execute(
        UploadAvatarInput(
            user_id=UUID(payload["sub"]),
            library_id=UUID(payload["library_id"]),
            image_bytes=image_bytes,
            content_type=file.content_type or "",
        )
    )
    result = await GetUserUseCase(user_repo, membership_repo).execute(
        GetUserInput(user_id=UUID(payload["sub"]), requester_library_id=UUID(payload["library_id"]))
    )
    return UserResponse.model_validate(result)


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile picture",
    description="Remove the current user's profile picture."
)
async def delete_avatar(
    payload: JWTPayload = Depends(require_library_context),
    use_case: DeleteAvatarUseCase = Depends(get_delete_avatar_use_case),
) -> None:
    await use_case.execute(
        DeleteAvatarInput(
            user_id=UUID(payload["sub"]),
            library_id=UUID(payload["library_id"]),
        )
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete user from library. Requires admin role."
)
async def delete_user(
    user_id: UUID,
    payload: JWTPayload = Depends(require_role("admin")),
    use_case: DeleteUserUseCase = Depends(get_delete_user_use_case),
) -> None:
    await use_case.execute(
        DeleteUserInput(user_id=user_id, requester_library_id=UUID(payload["library_id"]))
    )
