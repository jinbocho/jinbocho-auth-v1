from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_token_service, get_refresh_token_repository
from app.api.v1.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.application.use_cases.auth import (
    RegisterFamilyInput,
    RegisterFamilyUseCase,
    LoginInput,
    LoginUseCase,
    RefreshTokenInput,
    RefreshTokenUseCase,
    LogoutInput,
    LogoutUseCase,
    RequestPasswordResetUseCase,
    RequestPasswordResetInput,
    ResetPasswordUseCase,
    ResetPasswordInput,
)
from app.application.services import TokenService
from app.config import settings
from app.infrastructure.email import EmailSender
from app.infrastructure.repositories import (
    SQLAlchemyFamilyRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyPasswordResetTokenRepository,
)
from app.limiter import limiter

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new family",
    description="Register a new family and create the admin user. Requires valid email and password.",
    responses={
        409: {"description": "Email already registered"},
    }
)
@limiter.limit("5/minute")
async def register_family(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = RegisterFamilyUseCase(SQLAlchemyFamilyRepository(db), user_repo)
    try:
        result = await use_case.execute(
            RegisterFamilyInput(
                family_name=body.family_name,
                admin_email=body.admin_email,
                admin_password=body.admin_password,
                admin_full_name=body.admin_full_name,
            )
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return RegisterResponse(family_id=result.family_id, user_id=result.user_id)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user with email and password. Returns access and refresh tokens.",
    responses={
        401: {"description": "Invalid credentials or user inactive"},
    }
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service),
    refresh_token_repo = Depends(get_refresh_token_repository),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = LoginUseCase(user_repo, refresh_token_repo, token_service)
    try:
        result = await use_case.execute(LoginInput(email=body.email, password=body.password))
        await db.commit()
        return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)
    except LookupError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PermissionError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Use refresh token to obtain a new access token. Old refresh token is revoked.",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    }
)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service),
    refresh_token_repo = Depends(get_refresh_token_repository),
):
    user_repo = SQLAlchemyUserRepository(db)
    use_case = RefreshTokenUseCase(user_repo, refresh_token_repo, token_service)
    try:
        result = await use_case.execute(RefreshTokenInput(refresh_token=body.refresh_token))
        await db.commit()
        return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)
    except LookupError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PermissionError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Revoke refresh token and logout user. No response body.",
)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    refresh_token_repo = Depends(get_refresh_token_repository),
) -> Response:
    use_case = LogoutUseCase(refresh_token_repo)
    await use_case.execute(LogoutInput(refresh_token=body.refresh_token))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Request password reset",
    description="Send a password reset link to the given email. Always returns 204 to prevent email enumeration.",
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    email_sender = EmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.email_from,
        timeout_seconds=settings.smtp_timeout_seconds,
    )
    use_case = RequestPasswordResetUseCase(
        SQLAlchemyUserRepository(db),
        SQLAlchemyPasswordResetTokenRepository(db),
        email_sender,
    )
    await use_case.execute(RequestPasswordResetInput(email=body.email))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset password",
    description="Consume a reset token and set a new password. Token is single-use and expires in 15 minutes.",
    responses={
        400: {"description": "Invalid, expired, or already-used token"},
    },
)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    use_case = ResetPasswordUseCase(
        SQLAlchemyUserRepository(db),
        SQLAlchemyPasswordResetTokenRepository(db),
    )
    try:
        await use_case.execute(ResetPasswordInput(token=body.token, new_password=body.new_password))
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
