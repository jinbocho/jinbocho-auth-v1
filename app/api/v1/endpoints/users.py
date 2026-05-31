from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_payload, get_db, require_role
from app.api.v1.schemas.user_schemas import UserResponse, UserCreate, UserUpdate
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
)
from app.infrastructure.repositories import SQLAlchemyUserRepository

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
    summary="Create new user",
    description="Create new user in family. Requires admin role."
)
async def create_user(
    request: UserCreate,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = CreateUserUseCase(user_repo)
    try:
        result = await use_case.execute(
            CreateUserInput(
                family_id=UUID(payload["family_id"]),
                email=request.email,
                password=request.password,
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
    description="List all users in the family. Requires admin role."
)
async def list_users(
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = ListUsersUseCase(user_repo)
    result = await use_case.execute(ListUsersInput(family_id=UUID(payload["family_id"])))
    return result.users


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
            )
        )
        await db.commit()
        return UserResponse(**result.__dict__)
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


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
