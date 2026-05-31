import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.domain.entities import User, Family, RefreshToken
from app.domain.repositories import UserRepository, FamilyRepository, RefreshTokenRepository


class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}

    async def save(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def find_by_email(self, email: str) -> User | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def find_by_id(self, id) -> User | None:
        return self.users.get(id)


class MockFamilyRepository(FamilyRepository):
    def __init__(self):
        self.families = {}

    async def save(self, family: Family) -> Family:
        self.families[family.id] = family
        return family

    async def find_by_id(self, id) -> Family | None:
        return self.families.get(id)


class MockRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self):
        self.tokens = {}

    async def save(self, token: RefreshToken) -> RefreshToken:
        self.tokens[token.token_hash] = token
        return token

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.tokens.get(token_hash)

    async def revoke(self, token_hash: str) -> None:
        if token_hash in self.tokens:
            token = self.tokens[token_hash]
            token.revoked_at = datetime.now(timezone.utc)

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [h for h, t in self.tokens.items() if t.expires_at < now]
        for h in expired:
            del self.tokens[h]
        return len(expired)


@pytest.fixture
def mock_user_repo():
    return MockUserRepository()


@pytest.fixture
def mock_family_repo():
    return MockFamilyRepository()


@pytest.fixture
def mock_refresh_token_repo():
    return MockRefreshTokenRepository()


@pytest.fixture
def test_family():
    return Family(id=uuid4(), name="Test Family")


@pytest.fixture
def test_user(test_family):
    return User(
        id=uuid4(),
        family_id=test_family.id,
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
        role="admin",
    )
