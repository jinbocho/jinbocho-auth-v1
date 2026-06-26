import pytest
from uuid import uuid4

from app.application.use_cases.auth import (
    LoginUseCase,
    LoginInput,
    RefreshTokenUseCase,
    RefreshTokenInput,
    LogoutUseCase,
    LogoutInput,
)
from app.domain.entities import User, RefreshToken, UserRole


@pytest.mark.asyncio
async def test_login_successful(mock_user_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test successful login creates tokens and persists refresh token."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=password_hasher.hash(password),
        full_name="Test User",
        role=UserRole.ADMIN,
    )
    await mock_user_repo.save(user)

    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service, password_hasher)

    result = await use_case.execute(LoginInput(email=user.email, password=password))

    assert result.access_token
    assert result.refresh_token
    assert len(mock_refresh_token_repo.tokens) == 1


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_user_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test login with invalid credentials raises LookupError."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=password_hasher.hash(password),
        full_name="Test User",
        role=UserRole.ADMIN,
    )
    await mock_user_repo.save(user)

    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service, password_hasher)

    with pytest.raises(LookupError):
        await use_case.execute(LoginInput(email=user.email, password="wrong_password"))


@pytest.mark.asyncio
async def test_login_inactive_user(mock_user_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test login with inactive user raises PermissionError."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=password_hasher.hash(password),
        full_name="Test User",
        role=UserRole.ADMIN,
        is_active=False,
    )
    await mock_user_repo.save(user)

    use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(LoginInput(email=user.email, password=password))


@pytest.mark.asyncio
async def test_refresh_token_success(mock_user_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test successful token refresh rotates tokens."""
    password = "test_password_123"
    user = User(
        id=uuid4(),
        family_id=uuid4(),
        email="test@example.com",
        password_hash=password_hasher.hash(password),
        full_name="Test User",
        role=UserRole.ADMIN,
    )
    await mock_user_repo.save(user)

    login_use_case = LoginUseCase(mock_user_repo, mock_refresh_token_repo, token_service, password_hasher)
    login_result = await login_use_case.execute(LoginInput(email=user.email, password=password))

    refresh_use_case = RefreshTokenUseCase(mock_user_repo, mock_refresh_token_repo, token_service)
    refresh_result = await refresh_use_case.execute(
        RefreshTokenInput(refresh_token=login_result.refresh_token)
    )

    assert refresh_result.access_token
    assert refresh_result.refresh_token
    assert refresh_result.refresh_token != login_result.refresh_token
    assert len(mock_refresh_token_repo.tokens) == 2  # Old + new


@pytest.mark.asyncio
async def test_refresh_token_invalid(mock_user_repo, mock_refresh_token_repo, token_service):
    """Test refresh with invalid token raises LookupError."""
    use_case = RefreshTokenUseCase(mock_user_repo, mock_refresh_token_repo, token_service)

    with pytest.raises(LookupError):
        await use_case.execute(RefreshTokenInput(refresh_token="invalid_token"))


@pytest.mark.asyncio
async def test_logout_success(mock_refresh_token_repo, token_service):
    """Test logout revokes refresh token."""
    refresh_token = "test_refresh_token_12345"
    token_hash = token_service.hash_token(refresh_token)

    token = RefreshToken(
        user_id=uuid4(),
        token_hash=token_hash,
        expires_at=token_service.utcnow(),
    )
    await mock_refresh_token_repo.save(token)

    use_case = LogoutUseCase(mock_refresh_token_repo, token_service)
    await use_case.execute(LogoutInput(refresh_token=refresh_token))

    stored_token = await mock_refresh_token_repo.find_by_hash(token_hash)
    assert stored_token.revoked_at is not None
