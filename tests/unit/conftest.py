import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.application.ports import EmailService
from app.domain.entities import Library, LibraryMembership, MembershipStatus, PasswordResetToken, RefreshToken, User, UserRole
from app.domain.repositories import (
    LibraryRepository,
    MembershipRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.infrastructure.security import BcryptPasswordHasher


class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
        # Optional collaborator, wired up by tests that exercise
        # search_active_excluding_library — mirrors the real repository's
        # SQL join against membership rows without requiring every other
        # test in the suite to construct one.
        self.membership_repo: MembershipRepository | None = None

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

    async def find_by_library(self, library_id) -> list[User]:
        return [u for u in self.users.values() if u.library_id == library_id]

    async def search_active_excluding_library(self, query: str, exclude_library_id, limit: int) -> list[User]:
        excluded_ids: set = set()
        if self.membership_repo is not None:
            non_revoked = [
                MembershipStatus.INVITED, MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED,
            ]
            memberships = await self.membership_repo.find_by_library(exclude_library_id, non_revoked)
            excluded_ids = {m.user_id for m in memberships}
        needle = query.lower()
        matches = [
            u for u in self.users.values()
            if u.is_active and u.id not in excluded_ids
            and (needle in u.full_name.lower() or needle in u.email.lower())
        ]
        matches.sort(key=lambda u: u.full_name.lower())
        return matches[:limit]

    async def delete(self, id) -> None:
        self.users.pop(id, None)


class MockLibraryRepository(LibraryRepository):
    def __init__(self):
        self.libraries = {}

    async def save(self, library: Library) -> Library:
        self.libraries[library.id] = library
        return library

    async def find_by_id(self, id) -> Library | None:
        return self.libraries.get(id)

    async def delete(self, id) -> None:
        self.libraries.pop(id, None)


class MockMembershipRepository(MembershipRepository):
    def __init__(self):
        self.memberships = {}

    async def save(self, membership: LibraryMembership) -> LibraryMembership:
        self.memberships[membership.id] = membership
        return membership

    async def find_by_id(self, id) -> LibraryMembership | None:
        return self.memberships.get(id)

    async def find_by_user_and_library(self, user_id, library_id) -> LibraryMembership | None:
        for m in self.memberships.values():
            if m.user_id == user_id and m.library_id == library_id:
                return m
        return None

    async def find_by_user(self, user_id, statuses: list[MembershipStatus] | None = None) -> list[LibraryMembership]:
        result = [m for m in self.memberships.values() if m.user_id == user_id]
        if statuses:
            result = [m for m in result if m.status in statuses]
        return result

    async def find_by_library(self, library_id, statuses: list[MembershipStatus] | None = None) -> list[LibraryMembership]:
        result = [m for m in self.memberships.values() if m.library_id == library_id]
        if statuses:
            result = [m for m in result if m.status in statuses]
        return result

    async def delete(self, id) -> None:
        self.memberships.pop(id, None)


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

    async def revoke_all_for_users(self, user_ids: list) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for token in self.tokens.values():
            if token.user_id in user_ids and token.revoked_at is None:
                token.revoked_at = now
                count += 1
        return count

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

    async def invalidate_pending(self, user_id, purpose, used_at) -> None:
        for token in self.tokens.values():
            if token.user_id == user_id and token.purpose == purpose and token.used_at is None:
                token.used_at = used_at

    async def cleanup_expired(self) -> int:
        return 0


class FakeEmailSender(EmailService):
    """Captures sent messages instead of touching SMTP/stdout, for assertions in tests."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_password_setup_link(
        self, to_email: str, link: str, purpose: str = "reset", language: str | None = None
    ) -> None:
        self.sent.append({"to_email": to_email, "link": link, "purpose": purpose, "language": language})

    def send_welcome_email(
        self, to_email: str, library_name: str, link: str, language: str | None = None
    ) -> None:
        self.sent.append(
            {"to_email": to_email, "library_name": library_name, "link": link, "purpose": "welcome", "language": language}
        )

    def send_library_invite_email(
        self, to_email: str, library_name: str, inviter_name: str, link: str, language: str | None = None
    ) -> None:
        self.sent.append(
            {
                "to_email": to_email,
                "library_name": library_name,
                "inviter_name": inviter_name,
                "link": link,
                "purpose": "library_invite",
                "language": language,
            }
        )

    def send_loan_reminder(
        self,
        to_email: str,
        book_title: str,
        borrower_name: str,
        due_date: datetime,
        language: str | None = None,
    ) -> None:
        self.sent.append(
            {
                "to_email": to_email,
                "book_title": book_title,
                "borrower_name": borrower_name,
                "due_date": due_date,
                "purpose": "loan_reminder",
                "language": language,
            }
        )


# static guard: mypy fails here if FakeEmailSender diverges from EmailService port
_check: EmailService = FakeEmailSender()


@pytest.fixture(scope="session")
def test_settings():
    """Build a Settings object without reading from .env so unit tests run in
    any environment (CI, fresh clone) without a configured .env file."""
    from app.config import Settings

    return Settings.model_construct(
        debug=False,
        database_url="postgresql+asyncpg://not-used-in-unit-tests/test",
        jwt_secret_key="unit-test-only-not-a-real-secret-key-32c",
        jwt_algorithm="HS256",
        jwt_issuer="jinbocho-auth",
        jwt_audience="jinbocho",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
        password_reset_expire_minutes=15,
        invite_expire_minutes=10080,
        frontend_base_url="http://localhost:5173",
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        smtp_timeout_seconds=10,
        email_from="noreply@test.local",
        token_cleanup_interval_hours=1,
        internal_service_token="",
    )


@pytest.fixture
def token_service(test_settings):
    from app.application.services import TokenService
    return TokenService(test_settings)


@pytest.fixture
def password_hasher():
    return BcryptPasswordHasher()


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
def mock_library_repo():
    return MockLibraryRepository()


@pytest.fixture
def mock_membership_repo():
    return MockMembershipRepository()


@pytest.fixture
def mock_refresh_token_repo():
    return MockRefreshTokenRepository()


@pytest.fixture
def test_library():
    return Library(id=uuid4(), name="Test Library")


@pytest.fixture
def test_user(test_library):
    return User(
        id=uuid4(),
        library_id=test_library.id,
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
        role=UserRole.ADMIN,
    )
