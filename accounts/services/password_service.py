from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class PasswordService:
    """
    Centralized service for password hashing, verification, and complexity validation.
    Guarantees that raw passwords are never persisted or logged, and enforces Django's
    configured AUTH_PASSWORD_VALIDATORS.
    """

    @classmethod
    def hash_password(cls, raw_password: str) -> str:
        """Generates a standard Django pbkdf2_sha256 hash from a raw password."""
        if not raw_password:
            raise ValueError("Password cannot be empty.")
        return make_password(raw_password)

    @classmethod
    def verify_password(cls, raw_password: str, hashed_password: str) -> bool:
        """Verifies a candidate raw password against a stored hash in constant time."""
        if not raw_password or not hashed_password:
            return False
        return check_password(raw_password, hashed_password)

    @classmethod
    def validate_password_strength(cls, raw_password: str, user=None) -> list[str]:
        """
        Runs configured Django password validators against the raw password.
        Returns a list of human-readable error messages (empty list if password is valid).
        """
        if not raw_password:
            return ["Password cannot be empty."]
        try:
            validate_password(raw_password, user=user)
            return []
        except ValidationError as error:
            return list(error.messages)

    @classmethod
    def apply_password_to_user(cls, user, raw_password: str) -> None:
        """
        Applies a new password to an AuthUser instance, populating both `password`
        and `password_hash` to ensure full compatibility with the existing database.
        """
        hashed = cls.hash_password(raw_password)
        user.password = hashed
        user.password_hash = hashed
