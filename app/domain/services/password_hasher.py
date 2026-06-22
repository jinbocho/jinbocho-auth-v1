from typing import Protocol


class PasswordHasher(Protocol):
    """Port for password hashing. The concrete algorithm (bcrypt, argon2,
    ...) is an infrastructure detail; use cases only depend on this."""

    def hash(self, plain: str) -> str: ...

    def verify(self, plain: str, hashed: str) -> bool: ...
