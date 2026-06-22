from passlib.context import CryptContext  # type: ignore[import-untyped]


class BcryptPasswordHasher:
    """Implements app.domain.services.PasswordHasher with passlib/bcrypt."""

    def __init__(self) -> None:
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain: str) -> str:
        return str(self._context.hash(plain))

    def verify(self, plain: str, hashed: str) -> bool:
        return bool(self._context.verify(plain, hashed))
