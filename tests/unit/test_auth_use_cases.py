import pytest
from uuid import uuid4

from app.application.services import TokenService
from app.application.use_cases.auth import (
    LoginUseCase,
    LoginInput,
    RefreshTokenUseCase,
    RefreshTokenInput,
    LogoutUseCase,
    LogoutInput,
    pwd_context,
)
from app.config import settings
from app.domain.entities import User, RefreshToken
from tests.unit.conftest import MockUserRepository, MockRefreshTokenRepository


@pytest.mark.asyncio
async def test_login_successful(mock_user_repo, mock_refresh_token_repo):
    """Test successful login creates tokens and persists refresh token."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=pwd_context.hash(password),
        full_name="Test User",
        role="admin",
    )
    await mock_user_repo.save(user)

    token_service = TokenService(settings)
    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service)

    result = await use_case.execute(LoginInput(email=user.email, password=password))

    assert result.access_token
    assert result.refresh_token
    assert len(mock_refresh_token_repo.tokens) == 1


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_user_repo, mock_refresh_token_repo):
    """Test login with invalid credentials raises LookupError."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=pwd_context.hash(password),
        full_name="Test User",
        role="admin",
    )
    await mock_user_repo.save(user)

    token_service = TokenService(settings)
    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service)

    with pytest.raises(LookupError):
        await use_case.execute(LoginInput(email=user.email, password="wrong_password"))


@pytest.mark.asyncio
async def test_login_inactive_user(mock_user_repo, mock_refresh_token_repo):
    """Test login with inactive user raises PermissionError."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=pwd_context.hash(password),
        full_name="Test User",
        role="admin",
        is_active=False,
    )
    await mock_user_repo.save(user)

    token_service = TokenService(settings)
    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service)

    with pytest.raises(PermissionError):
        await use_case.execute(LoginInput(email=user.email, password=password))


@pytest.mark.asyncio
async def test_refresh_token_success(mock_user_repo, mock_refresh_token_repo):
    """Test successful token refresh rotates tokens."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=pwd_context.hash(password),
        full_name="Test User",
        role="admin",
    )
    await mock_user_repo.save(user)

    token_service = TokenService(settings)

    # First login to get refresh token
    login_use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service)
    login_result = await login_use_case.execute(LoginInput(email=user.email, password=password))

    # Then refresh
    refresh_use_case = RefreshTokenUseCase(mock_user_repo, mock_refresh_token_repo, token_service)
    refresh_result = await refresh_use_case.execute(
        RefreshTokenInput(refresh_token=login_result.refresh_token)
    )

    assert refresh_result.access_token
    assert refresh_result.refresh_token
    assert refresh_result.refresh_token != login_result.refresh_token
    assert len(mock_refresh_token_repo.tokens) == 2  # Old + new


@pytest.mark.asyncio
async def test_refresh_token_invalid(mock_user_repo, mock_refresh_token_repo):
    """Test refresh with invalid token raises LookupError."""
    token_service = TokenService(settings)
    use_case = RefreshTokenUseCase(mock_user_repo, mock_refresh_token_repo, token_service)

    with pytest.raises(LookupError):
        await use_case.execute(RefreshTokenInput(refresh_token="invalid_token"))


@pytest.mark.asyncio
async def test_logout_success(mock_refresh_token_repo):
    """Test logout revokes refresh token."""
    token_service = TokenService(settings)
    refresh_token = "test_refresh_token_12345"
    token_hash = token_service.hash_token(refresh_token)

    token = RefreshToken(
        user_id=uuid4(),
        token_hash=token_hash,
        expires_at=token_service.utcnow(),
    )
    await mock_refresh_token_repo.save(token)

    use_case = LogoutUseCase(mock_refresh_token_repo)
    await use_case.execute(LogoutInput(refresh_token=refresh_token))

    stored_token = await mock_refresh_token_repo.find_by_hash(token_hash)
    assert stored_token.revoked_at is not None
