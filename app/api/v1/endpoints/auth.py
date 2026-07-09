from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    get_confirm_email_change_use_case,
    get_forgot_password_use_case,
    get_login_use_case,
    get_logout_use_case,
    get_refresh_token_use_case,
    get_register_library_use_case,
    get_reset_password_use_case,
)
from app.api.v1.schemas.auth_schemas import (
    ConfirmEmailChangeRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.application.use_cases.auth import (
    LoginInput,
    LoginUseCase,
    LogoutInput,
    LogoutUseCase,
    RefreshTokenInput,
    RefreshTokenUseCase,
    RegisterLibraryInput,
    RegisterLibraryUseCase,
    RequestPasswordResetInput,
    RequestPasswordResetUseCase,
    ResetPasswordInput,
    ResetPasswordUseCase,
)
from app.application.use_cases.users import ConfirmEmailChangeInput, ConfirmEmailChangeUseCase
from app.limiter import limiter

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new library",
    description="Register a new library and create the admin user. Requires valid email and password.",
    responses={
        409: {"description": "Email already registered"},
    }
)
@limiter.limit("5/minute")
async def register_library(
    request: Request,
    body: RegisterRequest,
    use_case: RegisterLibraryUseCase = Depends(get_register_library_use_case),
) -> RegisterResponse:
    result = await use_case.execute(
        RegisterLibraryInput(
            library_name=body.library_name,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            admin_full_name=body.admin_full_name,
            accepted_privacy_version=body.accepted_privacy_version,
            accepted_terms_version=body.accepted_terms_version,
        )
    )
    return RegisterResponse(library_id=result.library_id, user_id=result.user_id)


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
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> TokenResponse:
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
    use_case: RefreshTokenUseCase = Depends(get_refresh_token_use_case),
) -> TokenResponse:
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
    use_case: LogoutUseCase = Depends(get_logout_use_case),
) -> Response:
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
    use_case: RequestPasswordResetUseCase = Depends(get_forgot_password_use_case),
) -> Response:
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
    use_case: ResetPasswordUseCase = Depends(get_reset_password_use_case),
) -> Response:
    await use_case.execute(ResetPasswordInput(token=body.token, new_password=body.new_password))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/confirm-email-change",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm an email address change",
    description="Consume an email-change verification token, sent to the new address by "
    "POST /users/me/email/change. Token is single-use and expires in 30 minutes. "
    "Unauthenticated: the token itself is the credential, since the link may be opened on a "
    "different device/session than the one that requested the change.",
    responses={
        400: {"description": "Invalid, expired, or already-used token"},
        409: {"description": "Email already registered to another account"},
    },
)
@limiter.limit("5/minute")
async def confirm_email_change(
    request: Request,
    body: ConfirmEmailChangeRequest,
    use_case: ConfirmEmailChangeUseCase = Depends(get_confirm_email_change_use_case),
) -> Response:
    await use_case.execute(ConfirmEmailChangeInput(token=body.token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
