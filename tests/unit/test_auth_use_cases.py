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
from app.domain.entities import LibraryMembership, MembershipStatus, User, RefreshToken, UserRole


async def _make_user_with_membership(mock_user_repo, mock_membership_repo, password_hasher, password, **overrides):
    library_id = overrides.pop("library_id", uuid4())
    role = overrides.pop("role", UserRole.ADMIN)
    user = User(
        id=uuid4(),
        library_id=library_id,
        email=overrides.pop("email", "test@example.com"),
        password_hash=password_hasher.hash(password),
        full_name="Test User",
        role=role,
        last_selected_library_id=library_id,
        **overrides,
    )
    await mock_user_repo.save(user)
    await mock_membership_repo.save(
        LibraryMembership(user_id=user.id, library_id=library_id, role=role, status=MembershipStatus.ACTIVE)
    )
    return user


@pytest.mark.asyncio
async def test_login_successful(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test successful login creates tokens and persists refresh token, auto-selecting the single library."""
    password = "test_password_123"
    user = await _make_user_with_membership(mock_user_repo, mock_membership_repo, password_hasher, password)

    use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)

    result = await use_case.execute(LoginInput(email=user.email, password=password))

    assert result.access_token
    assert result.refresh_token
    assert result.library_id == str(user.library_id)
    assert result.role == user.role.value
    assert len(mock_refresh_token_repo.tokens) == 1


@pytest.mark.asyncio
async def test_login_with_no_active_memberships_returns_context_less_token(
    mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service
):
    password = "test_password_123"
    user = User(
        id=uuid4(),
        library_id=uuid4(),
        email="orphan@example.com",
        password_hash=password_hasher.hash(password),
        full_name="Orphan User",
        role=UserRole.VIEWER,
    )
    await mock_user_repo.save(user)  # no membership created

    use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)
    result = await use_case.execute(LoginInput(email=user.email, password=password))

    assert result.access_token
    assert result.library_id is None
    assert result.role is None


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test login with invalid credentials raises LookupError."""
    password = "test_password_123"
    user = await _make_user_with_membership(mock_user_repo, mock_membership_repo, password_hasher, password)

    use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)

    with pytest.raises(LookupError):
        await use_case.execute(LoginInput(email=user.email, password="wrong_password"))


@pytest.mark.asyncio
async def test_login_inactive_user(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test login with inactive user raises PermissionError."""
    password = "test_password_123"
    user = await _make_user_with_membership(
        mock_user_repo, mock_membership_repo, password_hasher, password, is_active=False
    )

    use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)

    with pytest.raises(PermissionError):
        await use_case.execute(LoginInput(email=user.email, password=password))


@pytest.mark.asyncio
async def test_refresh_token_success(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service):
    """Test successful token refresh rotates tokens and keeps the library context."""
    password = "test_password_123"
    user = await _make_user_with_membership(mock_user_repo, mock_membership_repo, password_hasher, password)

    login_use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)
    login_result = await login_use_case.execute(LoginInput(email=user.email, password=password))

    refresh_use_case = RefreshTokenUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service)
    refresh_result = await refresh_use_case.execute(
        RefreshTokenInput(refresh_token=login_result.refresh_token)
    )

    assert refresh_result.access_token
    assert refresh_result.refresh_token
    assert refresh_result.refresh_token != login_result.refresh_token
    assert refresh_result.library_id == str(user.library_id)
    assert len(mock_refresh_token_repo.tokens) == 2  # Old + new


@pytest.mark.asyncio
async def test_refresh_token_drops_context_when_membership_revoked(
    mock_user_repo, mock_membership_repo, mock_refresh_token_repo, password_hasher, token_service
):
    """A membership revoked mid-session must not survive the next refresh."""
    password = "test_password_123"
    user = await _make_user_with_membership(mock_user_repo, mock_membership_repo, password_hasher, password)

    login_use_case = LoginUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service, password_hasher)
    login_result = await login_use_case.execute(LoginInput(email=user.email, password=password))

    membership = await mock_membership_repo.find_by_user_and_library(user.id, user.library_id)
    membership.status = MembershipStatus.REVOKED
    await mock_membership_repo.save(membership)

    refresh_use_case = RefreshTokenUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service)
    refresh_result = await refresh_use_case.execute(
        RefreshTokenInput(refresh_token=login_result.refresh_token)
    )

    assert refresh_result.library_id is None
    assert refresh_result.role is None


@pytest.mark.asyncio
async def test_refresh_token_invalid(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service):
    """Test refresh with invalid token raises LookupError."""
    use_case = RefreshTokenUseCase(mock_user_repo, mock_membership_repo, mock_refresh_token_repo, token_service)

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
