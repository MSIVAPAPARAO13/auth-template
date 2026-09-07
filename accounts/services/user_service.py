import re
from django.utils import timezone
from django.db import transaction
from accounts.models import AuthUser


class UserService:
    """
    Service responsible for user-related business operations:
    - Deterministic, collision-safe username generation
    - Name splitting
    - Safe AuthUser creation with synchronized password hashes
    """

    @classmethod
    def generate_unique_username(cls, email: str, full_name: str = "") -> str:
        """
        Generates a clean, deterministic, collision-safe username.
        Example:
          'john.doe@company.com' -> 'john_doe'
          If taken -> 'john_doe2', 'john_doe3', etc.
        """
        base = email.split("@")[0].lower()
        base = re.sub(r"[^a-z0-9_]", "_", base).strip("_")

        if not base:
            # Fallback to sanitized full_name if email prefix was empty/symbols
            base = re.sub(r"[^a-z0-9_]", "_", full_name.lower()).strip("_")

        if not base:
            base = "user"

        # Limit base length to 130 characters so numeric suffix fits well within 150
        base = base[:130]

        candidate = base
        suffix = 2
        while AuthUser.objects.filter(username=candidate).exists():
            candidate = f"{base}{suffix}"
            suffix += 1

        return candidate

    @classmethod
    def split_name(cls, full_name: str) -> tuple[str, str]:
        """Splits full_name into first_name and last_name."""
        clean = full_name.strip()
        if not clean:
            return "", ""
        parts = clean.split(" ", 1)
        first_name = parts[0][:150]
        last_name = parts[1][:150] if len(parts) > 1 else ""
        return first_name, last_name

    @classmethod
    def create_user_from_registration(
        cls,
        full_name: str,
        email: str,
        hashed_password: str,
        mobile: str | None = None,
        username: str | None = None,
    ) -> AuthUser:
        """
        Atomically creates a new AuthUser record from verified registration data.
        Ensures password and password_hash are identically populated with PBKDF2 hash.
        """
        clean_email = email.strip().lower()
        clean_mobile = mobile.strip() if mobile else None
        first_name, last_name = cls.split_name(full_name)

        if not username:
            username = cls.generate_unique_username(clean_email, full_name)

        with transaction.atomic():
            user = AuthUser.objects.create(
                full_name=full_name.strip()[:150],
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=clean_email,
                mobile=clean_mobile,
                password=hashed_password,
                password_hash=hashed_password,
                is_active=1,
                is_staff=0,
                is_superuser=0,
                date_joined=timezone.now(),
            )

        return user
