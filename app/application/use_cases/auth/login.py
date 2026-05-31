from dataclasses import dataclass
from datetime import timedelta

from passlib.context import CryptContext

from app.application.services import TokenService
from app.config import settings
from app.domain.entities import RefreshToken, User
from app.domain.repositories import RefreshTokenRepository, UserRepository


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class LoginInput:
    email: str
    password: str


@dataclass
class LoginOutput:
    access_token: str
    refresh_token: str


class LoginUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        token_service: TokenService,
    ):
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service

    async def execute(self, input: LoginInput) -> LoginOutput:
        user = await self._user_repo.find_by_email(input.email)
        if not user or not pwd_context.verify(input.password, user.password_hash):
            raise LookupError("Invalid credentials")
        if not user.is_active:
            raise PermissionError("User is inactive")

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, str(user.family_id), user.role
        )
        refresh_token = self._token_service.create_refresh_token()

        token_entity = RefreshToken(
            user_id=user.id,
            token_hash=self._token_service.hash_token(refresh_token),
            expires_at=self._token_service.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
        await self._refresh_token_repo.save(token_entity)

        return LoginOutput(access_token=access_token, refresh_token=refresh_token)
