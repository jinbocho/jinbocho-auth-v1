import logging
from dataclasses import dataclass
from datetime import timedelta

from app.application.services import TokenService
from app.domain.entities import RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from app.domain.repositories import RefreshTokenRepository, UserRepository
from app.domain.services import PasswordHasher

logger = logging.getLogger(__name__)


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
        password_hasher: PasswordHasher,
    ):
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._token_service = token_service
        self._password_hasher = password_hasher

    async def execute(self, input: LoginInput) -> LoginOutput:
        user = await self._user_repo.find_by_email(input.email)
        if not user or not self._password_hasher.verify(input.password, user.password_hash):
            logger.warning("Failed login attempt for email %s", input.email)
            raise InvalidCredentialsError("Invalid credentials")
        if not user.is_active:
            logger.warning("Login attempt by inactive user %s", user.id)
            raise InactiveUserError("User is inactive")

        access_token = self._token_service.create_access_token(
            str(user.id), user.email, str(user.family_id), user.role
        )
        refresh_token = self._token_service.create_refresh_token()

        token_entity = RefreshToken(
            user_id=user.id,
            token_hash=self._token_service.hash_token(refresh_token),
            expires_at=self._token_service.utcnow() + timedelta(days=self._token_service.refresh_token_expire_days),
        )
        await self._refresh_token_repo.save(token_entity)
        logger.info("User %s logged in", user.id)
        return LoginOutput(access_token=access_token, refresh_token=refresh_token)
