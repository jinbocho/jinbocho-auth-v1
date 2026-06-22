from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    get_email_sender,
    get_family_repository,
    get_password_hasher,
    get_password_reset_token_repository,
    get_refresh_token_repository,
    get_token_service,
    get_user_repository,
)
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
from app.domain.repositories import (
    FamilyRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.domain.services import PasswordHasher
from app.infrastructure.email import EmailSender
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
async def register_family(
    request: Request,
    body: RegisterRequest,
    family_repo: FamilyRepository = Depends(get_family_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    email_sender: EmailSender = Depends(get_email_sender),
) -> RegisterResponse:
    use_case = RegisterFamilyUseCase(family_repo, user_repo, password_hasher, email_sender)
    result = await use_case.execute(
        RegisterFamilyInput(
            family_name=body.family_name,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            admin_full_name=body.admin_full_name,
        )
    )
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
    user_repo: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> TokenResponse:
    use_case = LoginUseCase(user_repo, refresh_token_repo, token_service, password_hasher)
    result = await use_case.execute(LoginInput(email=body.email, password=body.password))
    return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)


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
    user_repo: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> TokenResponse:
    use_case = RefreshTokenUseCase(user_repo, refresh_token_repo, token_service)
    result = await use_case.execute(RefreshTokenInput(refresh_token=body.refresh_token))
    return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Revoke refresh token and logout user. No response body.",
)
async def logout(
    body: LogoutRequest,
    token_service: TokenService = Depends(get_token_service),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> Response:
    use_case = LogoutUseCase(refresh_token_repo, token_service)
    await use_case.execute(LogoutInput(refresh_token=body.refresh_token))
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
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    email_sender: EmailSender = Depends(get_email_sender),
    token_service: TokenService = Depends(get_token_service),
) -> Response:
    use_case = RequestPasswordResetUseCase(user_repo, reset_token_repo, email_sender, token_service)
    await use_case.execute(RequestPasswordResetInput(email=body.email))
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
    user_repo: UserRepository = Depends(get_user_repository),
    reset_token_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> Response:
    use_case = ResetPasswordUseCase(user_repo, reset_token_repo, token_service, password_hasher)
    await use_case.execute(ResetPasswordInput(token=body.token, new_password=body.new_password))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
