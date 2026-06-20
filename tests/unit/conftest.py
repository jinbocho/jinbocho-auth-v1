import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.domain.entities import User, Family, RefreshToken, PasswordResetToken
from app.domain.repositories import UserRepository, FamilyRepository, RefreshTokenRepository, PasswordResetTokenRepository


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

    async def find_by_family(self, family_id) -> list[User]:
        return [u for u in self.users.values() if u.family_id == family_id]

    async def delete(self, id) -> None:
        self.users.pop(id, None)


class MockFamilyRepository(FamilyRepository):
    def __init__(self):
        self.families = {}

    async def save(self, family: Family) -> Family:
        self.families[family.id] = family
        return family

    async def find_by_id(self, id) -> Family | None:
        return self.families.get(id)

    async def delete(self, id) -> None:
        self.families.pop(id, None)


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


class MockPasswordResetTokenRepository(PasswordResetTokenRepository):
    def __init__(self):
        self.tokens = {}

    async def save(self, token: PasswordResetToken) -> PasswordResetToken:
        self.tokens[token.id] = token
        return token

    async def find_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token_id, used_at) -> None:
        token = self.tokens.get(token_id)
        if token:
            token.used_at = used_at


class FakeEmailSender:
    """Captures sent links instead of touching SMTP/stdout, for assertions in tests."""

    def __init__(self):
        self.sent: list[dict] = []

    def send_password_setup_link(self, to_email, link, purpose="reset", language=None) -> None:
        self.sent.append({"to_email": to_email, "link": link, "purpose": purpose, "language": language})


@pytest.fixture
def mock_user_repo():
    return MockUserRepository()


@pytest.fixture
def mock_password_reset_token_repo():
    return MockPasswordResetTokenRepository()


@pytest.fixture
def fake_email_sender():
    return FakeEmailSender()


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
