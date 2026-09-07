import hashlib
import hmac
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from accounts.models import AuthOtps, AuthUser
from .delivery_service import OTPDeliveryRouter


class OTPService:
    """
    Cryptographically secure OTP lifecycle service.
    Handles generation, SHA-256 hashing, rate limiting, expiry, and concurrency-safe verification.
    """

    OTP_LENGTH = 6
    EXPIRY_MINUTES = 5
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60
    VALID_PURPOSES = ("login", "register", "reset_password")

    @classmethod
    def _hash_otp(cls, raw_otp: str) -> str:
        """Computes SHA-256 hexadecimal digest matching existing database schema."""
        return hashlib.sha256(raw_otp.strip().encode("utf-8")).hexdigest()

    @classmethod
    def can_resend(cls, identifier: str, purpose: str) -> tuple[bool, int]:
        """
        Enforces a 60-second cooldown between consecutive OTP generation requests.
        Returns:
            (can_resend: bool, seconds_remaining: int)
        """
        clean_id = identifier.strip().lower()
        recent_otp = (
            AuthOtps.objects.filter(identifier=clean_id, purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if not recent_otp:
            return True, 0

        elapsed = (timezone.now() - recent_otp.created_at).total_seconds()
        if elapsed < cls.RESEND_COOLDOWN_SECONDS:
            remaining = max(1, int(cls.RESEND_COOLDOWN_SECONDS - elapsed))
            return False, remaining

        return True, 0

    @classmethod
    def generate_and_send_otp(
        cls,
        identifier: str,
        purpose: str = "login",
        user: AuthUser | None = None,
        channel: str = "email",
    ) -> tuple[bool, str]:
        """
        Generates a 6-digit cryptographically secure OTP, stores its SHA-256 hash in auth_otps,
        and dispatches it via the explicitly chosen channel (Email, SMS, or WhatsApp).
        Does NOT return the raw OTP in the user-facing response to prevent secret leakage.

        Returns:
            (success: bool, message: str)
        """
        if purpose not in cls.VALID_PURPOSES:
            return False, f"Invalid OTP purpose: {purpose}"

        clean_id = identifier.strip().lower()

        # 1. Enforce resend cooldown
        can_send, remaining_seconds = cls.can_resend(clean_id, purpose)
        if not can_send:
            return (
                False,
                f"Please wait {remaining_seconds} seconds before requesting another verification code.",
            )

        # 2. Concurrency-safe invalidation of previous unused OTPs for this identifier & purpose
        with transaction.atomic():
            AuthOtps.objects.filter(
                identifier=clean_id,
                purpose=purpose,
                is_used=0,
            ).update(is_used=1)

            # 3. Cryptographically secure random 6-digit code (or standard 123456 in demo mode)
            from .delivery_service import is_demo_delivery_mode
            if is_demo_delivery_mode():
                raw_otp = "123456"
            else:
                raw_otp = f"{secrets.randbelow(900000) + 100000}"
            otp_hash = cls._hash_otp(raw_otp)
            expires_at = timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES)

            # 4. Resolve user reference if not provided (optional foreign key)
            if not user:
                user = (
                    AuthUser.objects.filter(email=clean_id).first()
                    or AuthUser.objects.filter(mobile=clean_id).first()
                )

            # 5. Persist the record in auth_otps
            otp_record = AuthOtps.objects.create(
                user=user,
                identifier=clean_id,
                purpose=purpose,
                otp_hash=otp_hash,
                expires_at=expires_at,
                is_used=0,
                attempt_count=0,
                created_at=timezone.now(),
            )

        # 6. Dispatch through the delivery router (never logging raw OTP)
        dispatch_success, dispatch_message = OTPDeliveryRouter.send_otp(
            identifier=clean_id,
            raw_otp=raw_otp,
            purpose=purpose,
            channel=channel,
        )

        if not dispatch_success:
            # Clean up undelivered OTP so an unreachable code is not left active
            # and the user is not locked out by the resend cooldown.
            try:
                otp_record.delete()
            except Exception:
                pass
            return False, dispatch_message

        return True, dispatch_message

    @classmethod
    def verify_otp(
        cls,
        identifier: str,
        candidate_otp: str,
        purpose: str = "login",
    ) -> tuple[bool, str, AuthOtps | None]:
        """
        Verifies the candidate OTP against the stored SHA-256 hash in auth_otps.
        Enforces single-use invalidation, expiration checks, attempt counts, and atomic locking.

        Returns:
            (is_valid: bool, message: str, otp_record: AuthOtps | None)
        """
        clean_id = identifier.strip().lower()
        candidate = candidate_otp.strip()

        if not candidate or len(candidate) != cls.OTP_LENGTH or not candidate.isdigit():
            return False, "Please enter a valid 6-digit numeric verification code.", None

        with transaction.atomic():
            # Concurrency protection: row-level lock on the active OTP record
            try:
                otp_record = (
                    AuthOtps.objects.select_for_update()
                    .filter(identifier=clean_id, purpose=purpose)
                    .order_by("-created_at")
                    .first()
                )
            except Exception:
                # In environments that do not support select_for_update, fall back to standard query
                otp_record = (
                    AuthOtps.objects.filter(identifier=clean_id, purpose=purpose)
                    .order_by("-created_at")
                    .first()
                )

            if not otp_record:
                return False, "No active verification code found. Please request a new code.", None

            # 1. Check if already used
            if bool(otp_record.is_used):
                return False, "This verification code has already been used. Please request a new code.", None

            # 2. Check expiration
            if otp_record.is_expired:
                otp_record.is_used = 1
                otp_record.save(update_fields=["is_used"])
                return False, "This verification code has expired. Please request a new code.", None

            # 3. Check attempt exhaustion
            if otp_record.attempt_count >= cls.MAX_ATTEMPTS:
                otp_record.is_used = 1
                otp_record.save(update_fields=["is_used"])
                return False, "Maximum attempts exceeded. This code is locked. Please request a new code.", None

            # 4. Constant-time hash comparison
            candidate_hash = cls._hash_otp(candidate)
            is_match = hmac.compare_digest(candidate_hash, otp_record.otp_hash)

            if is_match:
                otp_record.is_used = 1
                otp_record.save(update_fields=["is_used"])
                return True, "Verification code verified successfully.", otp_record
            else:
                otp_record.attempt_count += 1
                remaining = cls.MAX_ATTEMPTS - otp_record.attempt_count
                if remaining <= 0:
                    otp_record.is_used = 1
                    otp_record.save(update_fields=["attempt_count", "is_used"])
                    return False, "Incorrect verification code. Maximum attempts exceeded. Code is now locked.", None

                otp_record.save(update_fields=["attempt_count"])
                return False, f"Incorrect verification code. {remaining} attempt(s) remaining.", None
