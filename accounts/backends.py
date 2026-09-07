from django.contrib.auth.backends import BaseBackend
from accounts.models import AuthUser
from accounts.services.otp_service import OTPService


class AuthUserBackend(BaseBackend):
    """
    Custom authentication backend that safely authenticates against the unmanaged
    AuthUser model without requiring alterations to Django's AUTH_USER_MODEL.

    Supports:
      1. Username + Password
      2. Email + Password
      3. Mobile + Password
      4. Email + OTP
      5. Mobile + OTP
    """

    def authenticate(
        self,
        request,
        identifier: str | None = None,
        password: str | None = None,
        otp: str | None = None,
        purpose: str = "login",
        **kwargs,
    ) -> AuthUser | None:
        if not identifier:
            # Fallback to standard Django username kwarg if passed
            identifier = kwargs.get("username")

        if not identifier or (not password and not otp):
            return None

        clean_id = identifier.strip()

        # Resolve user by username, email, or mobile
        user = (
            AuthUser.objects.filter(username=clean_id).first()
            or AuthUser.objects.filter(email=clean_id.lower()).first()
            or AuthUser.objects.filter(mobile=clean_id).first()
        )
        if not user and "@" not in clean_id:
            from accounts.services.delivery_service import normalize_phone_number
            norm_phone = normalize_phone_number(clean_id)
            if norm_phone:
                user = AuthUser.objects.filter(mobile=norm_phone).first()

        if not user or not bool(user.is_active):
            return None

        # Path A: Password Verification
        if password:
            if not user.check_password(password):
                return None

        # Path B: OTP Verification
        elif otp:
            # For OTP authentication, verify against the identifier used (email or mobile)
            lookup_identifier = clean_id.lower() if "@" in clean_id else clean_id
            is_valid, _, _ = OTPService.verify_otp(
                identifier=lookup_identifier,
                candidate_otp=otp,
                purpose=purpose,
            )
            if not is_valid and "@" not in clean_id:
                from accounts.services.delivery_service import normalize_phone_number
                norm_phone = normalize_phone_number(clean_id)
                if norm_phone != lookup_identifier:
                    is_valid, _, _ = OTPService.verify_otp(
                        identifier=norm_phone,
                        candidate_otp=otp,
                        purpose=purpose,
                    )
            if not is_valid:
                return None

        user.backend = f"{self.__module__}.{self.__class__.__name__}"
        return user

    def get_user(self, user_id: int) -> AuthUser | None:
        """
        Retrieves the authenticated AuthUser instance for Django's AuthenticationMiddleware.
        Ensures `request.user` is populated with the correct AuthUser object across sessions.
        """
        try:
            return AuthUser.objects.filter(pk=user_id).first()
        except Exception:
            return None
