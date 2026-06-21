from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_payload, get_db, require_role
from app.api.v1.schemas.export_schemas import (
    FamilyDataExportResponse,
    FamilyExportItem,
    ImportUsersRequest,
    ImportUsersResponse,
    UserExportItem,
)
from app.api.v1.schemas.user_schemas import MeUpdate, UserResponse, UserCreate, UserUpdate
from app.application.use_cases.users import (
    CreateUserUseCase,
    CreateUserInput,
    GetUserUseCase,
    GetUserInput,
    ListUsersUseCase,
    ListUsersInput,
    UpdateUserUseCase,
    UpdateUserInput,
    DeleteUserUseCase,
    DeleteUserInput,
    ExportFamilyDataUseCase,
    ExportFamilyDataInput,
    ImportUsersUseCase,
    ImportUsersInput,
    ImportUserItem,
)
from app.config import settings
from app.infrastructure.email import EmailSender
from app.infrastructure.repositories import (
    SQLAlchemyFamilyRepository,
    SQLAlchemyPasswordResetTokenRepository,
    SQLAlchemyUserRepository,
)

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user's information."
)
async def get_me(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = GetUserUseCase(user_repo)
    try:
        result = await use_case.execute(
            GetUserInput(user_id=UUID(payload["sub"]), requester_family_id=UUID(payload["family_id"]))
        )
        return UserResponse(**result.__dict__)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


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
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    email_sender = EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.email_from,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
    use_case = CreateUserUseCase(user_repo, SQLAlchemyPasswordResetTokenRepository(db), email_sender)
    try:
        result = await use_case.execute(
            CreateUserInput(
                family_id=UUID(payload["family_id"]),
                email=request.email,
                full_name=request.full_name,
                role=request.role,
            )
        )
        await db.commit()
        return UserResponse(**result.__dict__)
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List family users",
    description="List all users in the family. Any authenticated family member "
    "(the roster is needed to show who is reading which book)."
)
async def list_users(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
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
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = UpdateUserUseCase(user_repo)
    try:
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
        await db.commit()
        return UserResponse(**result.__dict__)
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update user information. Requires admin role."
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = UpdateUserUseCase(user_repo)
    try:
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
        await db.commit()
        return UserResponse(**result.__dict__)
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get(
    "/export",
    response_model=FamilyDataExportResponse,
    summary="Export family roster",
    description="Export the family's identity and member roster for a full backup. "
    "Never includes password hashes — restored members set a fresh password via the "
    "same invite-by-email flow used for inviting a new member. Requires admin role."
)
async def export_family_data(
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    family_repo = SQLAlchemyFamilyRepository(db)
    user_repo = SQLAlchemyUserRepository(db)
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
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    email_sender = EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.email_from,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
    create_user = CreateUserUseCase(user_repo, SQLAlchemyPasswordResetTokenRepository(db), email_sender)
    update_user = UpdateUserUseCase(user_repo)
    use_case = ImportUsersUseCase(user_repo, create_user, update_user)

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
    await db.commit()
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
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = DeleteUserUseCase(user_repo)
    try:
        await use_case.execute(
            DeleteUserInput(user_id=user_id, requester_family_id=UUID(payload["family_id"]))
        )
        await db.commit()
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
