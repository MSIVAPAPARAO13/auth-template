import abc
import base64
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# In-memory test outboxes for automated testing (isolated SQLite runner)
sms_outbox = []
whatsapp_outbox = []


def is_test_environment() -> bool:
    """Returns True if running under automated test runner."""
    return (
        getattr(settings, "EMAIL_BACKEND", "") == "django.core.mail.backends.locmem.EmailBackend"
        or os.getenv("DJANGO_TESTING") == "1"
    )


def normalize_phone_number(raw_phone: str, default_country_code: str = "+91") -> str:
    """
    Normalizes a phone number to standard E.164 international format (e.g. +919876543210).
    Strips whitespace, parentheses, dashes, and ensures a leading '+' with 7-15 digits.
    """
    if not raw_phone:
        return ""
    cleaned = re.sub(r"[\s\-\(\)\.]", "", raw_phone.strip())
    if not cleaned.startswith("+"):
        # If 10 digits without leading code, apply default country code
        if len(cleaned) == 10 and cleaned.isdigit():
            cleaned = f"{default_country_code}{cleaned}"
        else:
            cleaned = f"+{cleaned}"
    return cleaned


def is_valid_e164(phone: str) -> bool:
    """Validates international E.164 phone number syntax (+ followed by 7 to 15 digits)."""
    return bool(re.match(r"^\+[1-9]\d{6,14}$", phone))


def mask_identifier(identifier: str, channel: str = "email") -> str:
    """
    Masks contact information for safe user-facing display and diagnostic logging.
    Email:  s******@gmail.com
    Phone:  ******1234 or +91 ******1234
    """
    if not identifier:
        return ""
    clean = identifier.strip()
    if channel == "email" or "@" in clean:
        try:
            user, domain = clean.split("@", 1)
            if len(user) <= 2:
                masked_user = user[0] + "*"
            else:
                masked_user = user[0] + "*" * (len(user) - 2) + user[-1]
            return f"{masked_user}@{domain}"
        except Exception:
            return "***@***"
    else:
        # Phone masking
        if len(clean) >= 6:
            last4 = clean[-4:]
            if clean.startswith("+"):
                country = clean[:3]
                return f"{country} ******{last4}"
            return f"******{last4}"
        return "******"


# ==============================================================================
# PROVIDER ADAPTERS (SMS & WHATSAPP)
# ==============================================================================

class BaseProviderAdapter(abc.ABC):
    @abc.abstractmethod
    def is_configured(self) -> bool:
        pass


class TwilioSMSProviderAdapter(BaseProviderAdapter):
    """
    HTTP REST adapter for Twilio SMS.
    Uses Python standard library urllib (no external dependencies required).
    """

    def is_configured(self) -> bool:
        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_num = getattr(settings, "TWILIO_PHONE_NUMBER", "")
        return bool(sid and token and from_num)

    def send_sms(self, to_phone: str, message: str) -> tuple[bool, str]:
        if is_test_environment():
            return True, "SMS dispatched successfully."

        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "").strip()
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "").strip()
        from_num = getattr(settings, "TWILIO_PHONE_NUMBER", "").strip()

        if not (sid and token and from_num):
            return False, "SMS provider is not configured."

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = urllib.parse.urlencode({
            "To": to_phone,
            "From": from_num,
            "Body": message,
        }).encode("utf-8")

        auth_header = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, "SMS dispatched successfully."
                return False, f"SMS provider returned status {resp.status}."
        except Exception as exc:
            # Safe diagnostic logging: never log auth tokens or raw OTP
            logger.error(
                "Twilio SMS delivery failure for %s [Error: %s]",
                mask_identifier(to_phone, "sms"),
                type(exc).__name__,
                exc_info=False,
            )
            return False, "Failed to deliver SMS message."


class TwilioWhatsAppProviderAdapter(BaseProviderAdapter):
    """
    HTTP REST adapter for Twilio WhatsApp.
    Uses Python standard library urllib (no external dependencies required).
    """

    def is_configured(self) -> bool:
        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_wa = getattr(settings, "TWILIO_WHATSAPP_FROM", "")
        return bool(sid and token and from_wa)

    def send_whatsapp(self, to_phone: str, message: str) -> tuple[bool, str]:
        if is_test_environment():
            return True, "WhatsApp message dispatched successfully."

        sid = getattr(settings, "TWILIO_ACCOUNT_SID", "").strip()
        token = getattr(settings, "TWILIO_AUTH_TOKEN", "").strip()
        from_wa = getattr(settings, "TWILIO_WHATSAPP_FROM", "").strip()

        if not (sid and token and from_wa):
            return False, "WhatsApp provider is not configured."

        # Format whatsapp: prefix
        from_target = from_wa if from_wa.startswith("whatsapp:") else f"whatsapp:{from_wa}"
        to_target = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = urllib.parse.urlencode({
            "To": to_target,
            "From": from_target,
            "Body": message,
        }).encode("utf-8")

        auth_header = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, "WhatsApp message dispatched successfully."
                return False, f"WhatsApp provider returned status {resp.status}."
        except Exception as exc:
            # Safe diagnostic logging: never log auth tokens or raw OTP
            logger.error(
                "Twilio WhatsApp delivery failure for %s [Error: %s]",
                mask_identifier(to_phone, "whatsapp"),
                type(exc).__name__,
                exc_info=False,
            )
            return False, "Failed to deliver WhatsApp message."


# ==============================================================================
# DELIVERY SERVICES
# ==============================================================================

class BaseDeliveryService(abc.ABC):
    """Abstract interface for dispatching OTP verification codes."""

    @abc.abstractmethod
    def send_otp(self, identifier: str, raw_otp: str, purpose: str) -> tuple[bool, str]:
        """
        Dispatches OTP to user identifier.
        Returns:
            (success: bool, user_facing_message: str)
        """
        pass

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Returns whether this delivery channel is configured and available."""
        pass


class EmailDeliveryService(BaseDeliveryService):
    """
    Delivers verification codes via Email using Django's configured email backend (SMTP, console, or locmem).
    Includes professional HTML + plaintext formatting with security advisories.
    """

    def is_configured(self) -> bool:
        # Email is always configured if SMTP credentials exist or in development/test modes
        if is_test_environment():
            return True
        backend = getattr(settings, "EMAIL_BACKEND", "")
        if "console" in backend:
            return True
        host_user = getattr(settings, "EMAIL_HOST_USER", "")
        host_pass = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        return bool(host_user and host_pass)

    def send_otp(self, identifier: str, raw_otp: str, purpose: str) -> tuple[bool, str]:
        clean_recipient = identifier.strip().lower()
        readable_purpose = purpose.replace("_", " ").title()
        if purpose == "register":
            readable_purpose = "Account Registration"
        elif purpose == "login":
            readable_purpose = "Sign In"
        elif purpose == "reset_password":
            readable_purpose = "Password Reset"

        subject = f"Your Verification Code: {raw_otp} — Authentication Platform"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "auth-platform@company.com")

        # Plaintext email content
        text_message = (
            f"Authentication Platform\n"
            f"========================================\n\n"
            f"Hello,\n\n"
            f"Your verification code for {readable_purpose} is:\n\n"
            f"    {raw_otp}\n\n"
            f"This code will expire in 5 minutes.\n\n"
            f"SECURITY NOTICE:\n"
            f"For your protection, never share this verification code with anyone. "
            f"Authentication Platform staff will never ask for your code.\n\n"
            f"If you did not request this verification code, please disregard this email.\n\n"
            f"— The Authentication Platform Team"
        )

        # Professional HTML email content
        html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Code</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8fafc; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="520px" cellspacing="0" cellpadding="0" border="0" style="max-width: 520px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="padding: 28px 32px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 600; letter-spacing: -0.02em;">Authentication Platform</h1>
              <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px;">Security & Identity Services</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 16px 0; font-size: 15px; color: #334155; line-height: 1.5;">Hello,</p>
              <p style="margin: 0 0 24px 0; font-size: 15px; color: #334155; line-height: 1.5;">
                Use the following 6-digit verification code to complete your <strong>{readable_purpose}</strong>:
              </p>
              <!-- OTP Box -->
              <div style="background-color: #f1f5f9; border-radius: 8px; border: 1px solid #cbd5e1; padding: 18px 24px; text-align: center; margin: 0 0 24px 0;">
                <span style="font-family: 'Courier New', Courier, monospace; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #0f172a;">{raw_otp}</span>
              </div>
              <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b; line-height: 1.5; text-align: center;">
                ⏱ This code is valid for <strong>5 minutes</strong> and can only be used once.
              </p>
              <!-- Security Warning -->
              <div style="background-color: #fef2f2; border-left: 3px solid #ef4444; padding: 12px 16px; border-radius: 4px; margin: 0 0 24px 0;">
                <p style="margin: 0; font-size: 12px; color: #991b1b; line-height: 1.4;">
                  <strong>Security Advisory:</strong> Never share this verification code with anyone. Platform support staff will never ask for your code.
                </p>
              </div>
              <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">
                If you did not request this verification code, no action is needed. You can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                &copy; Authentication Platform. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        try:
            send_mail(
                subject=subject,
                message=text_message,
                from_email=from_email,
                recipient_list=[clean_recipient],
                html_message=html_message,
                fail_silently=False,
            )
            return True, "Verification code sent to your email."
        except Exception as exc:
            # Safe diagnostic logging: log only recipient domain/masked address and exception type without secrets
            masked = mask_identifier(clean_recipient, "email")
            logger.error(
                "Email delivery failed for recipient %s [Error: %s]",
                masked,
                type(exc).__name__,
                exc_info=False,
            )
            return False, "We couldn't send the verification email right now. Please try again."


class SMSDeliveryService(BaseDeliveryService):
    """
    Delivers verification codes via SMS using a configurable SMS provider (e.g. Twilio).
    In automated tests, appends to the in-memory `sms_outbox`.
    """

    def __init__(self, adapter: BaseProviderAdapter | None = None):
        self._adapter = adapter or TwilioSMSProviderAdapter()

    def is_configured(self) -> bool:
        if is_test_environment():
            if hasattr(settings, "TEST_SMS_AVAILABLE") and not settings.TEST_SMS_AVAILABLE:
                return False
            return True
        return self._adapter.is_configured()

    def send_otp(self, identifier: str, raw_otp: str, purpose: str) -> tuple[bool, str]:
        normalized_phone = normalize_phone_number(identifier)
        if not is_valid_e164(normalized_phone):
            return False, "Please enter a valid mobile number with country code (e.g. +919876543210)."

        if not self.is_configured():
            return False, "SMS delivery is currently unavailable."

        message_body = (
            f"Your Authentication Platform verification code is: {raw_otp}. "
            f"Valid for 5 minutes. Do not share this code with anyone."
        )

        # Provider dispatch
        success, provider_msg = self._adapter.send_sms(normalized_phone, message_body)
        if not success:
            return False, "We couldn't send the SMS verification code right now. Please try again."

        # In-memory test capture for isolated test suite
        if is_test_environment():
            sms_outbox.append({
                "to": normalized_phone,
                "body": message_body,
                "raw_otp": raw_otp,
                "purpose": purpose,
            })

        return True, "Verification code sent to your mobile number."


class WhatsAppDeliveryService(BaseDeliveryService):
    """
    Delivers verification codes via WhatsApp using a configurable WhatsApp provider (e.g. Twilio).
    In automated tests, appends to the in-memory `whatsapp_outbox`.
    """

    def __init__(self, adapter: BaseProviderAdapter | None = None):
        self._adapter = adapter or TwilioWhatsAppProviderAdapter()

    def is_configured(self) -> bool:
        if is_test_environment():
            if hasattr(settings, "TEST_WHATSAPP_AVAILABLE") and not settings.TEST_WHATSAPP_AVAILABLE:
                return False
            return True
        return self._adapter.is_configured()

    def send_otp(self, identifier: str, raw_otp: str, purpose: str) -> tuple[bool, str]:
        normalized_phone = normalize_phone_number(identifier)
        if not is_valid_e164(normalized_phone):
            return False, "Please enter a valid mobile number with country code (e.g. +919876543210)."

        if not self.is_configured():
            return False, "WhatsApp delivery is currently unavailable."

        message_body = (
            f"Your Authentication Platform verification code is: {raw_otp}. "
            f"Valid for 5 minutes. Do not share this code with anyone."
        )

        # Provider dispatch
        success, provider_msg = self._adapter.send_whatsapp(normalized_phone, message_body)
        if not success:
            return False, "We couldn't send the WhatsApp verification code right now. Please try again."

        # In-memory test capture for isolated test suite
        if is_test_environment():
            whatsapp_outbox.append({
                "to": normalized_phone,
                "body": message_body,
                "raw_otp": raw_otp,
                "purpose": purpose,
            })

        return True, "Verification code sent to your WhatsApp."


def is_demo_delivery_mode() -> bool:
    """Returns True if demo OTP mode is enabled in settings and not running automated tests."""
    if is_test_environment():
        return False
    return getattr(settings, "OTP_DELIVERY_MODE", "demo") == "demo"


# ==============================================================================
# ROUTER
# ==============================================================================

class OTPDeliveryRouter:
    """
    Central delivery router dispatching OTP verification codes to the selected channel:
      1. Email
      2. SMS
      3. WhatsApp
    Strictly isolates channel execution to prevent accidental cross-dispatch.
    Supports transparent development/demo mode when providers are not yet configured.
    """

    _email_service = EmailDeliveryService()
    _sms_service = SMSDeliveryService()
    _whatsapp_service = WhatsAppDeliveryService()

    @classmethod
    def get_channel_status(cls) -> dict:
        """Returns configuration availability for each supported delivery channel."""
        demo = is_demo_delivery_mode()
        return {
            "email": {
                "available": True if demo else cls._email_service.is_configured(),
                "label": "Email Verification",
                "is_demo": demo and not cls._email_service.is_configured(),
            },
            "sms": {
                "available": True if demo else cls._sms_service.is_configured(),
                "label": "Mobile SMS",
                "is_demo": demo and not cls._sms_service.is_configured(),
            },
            "whatsapp": {
                "available": True if demo else cls._whatsapp_service.is_configured(),
                "label": "WhatsApp",
                "is_demo": demo and not cls._whatsapp_service.is_configured(),
            },
        }

    @classmethod
    def send_otp(
        cls,
        identifier: str,
        raw_otp: str,
        purpose: str,
        channel: str = "email",
    ) -> tuple[bool, str]:
        """
        Dispatches OTP to the explicitly requested channel.
        Guarantees channel isolation (Email never calls SMS/WhatsApp, etc.).
        In development/demo mode, provides clear test OTP feedback.
        """
        selected_channel = (channel or "email").strip().lower()
        demo = is_demo_delivery_mode()

        if selected_channel == "email":
            if demo and not cls._email_service.is_configured():
                return True, f"[DEVELOPMENT / DEMO MODE] Verification code sent to Email. Demo OTP: {raw_otp}"
            return cls._email_service.send_otp(identifier, raw_otp, purpose)
        elif selected_channel == "sms":
            if demo and not cls._sms_service.is_configured():
                return True, f"[DEVELOPMENT / DEMO MODE] Verification code sent to SMS. Demo OTP: {raw_otp}"
            return cls._sms_service.send_otp(identifier, raw_otp, purpose)
        elif selected_channel == "whatsapp":
            if demo and not cls._whatsapp_service.is_configured():
                return True, f"[DEVELOPMENT / DEMO MODE] Verification code sent to WhatsApp. Demo OTP: {raw_otp}"
            return cls._whatsapp_service.send_otp(identifier, raw_otp, purpose)
        else:
            return False, f"Unsupported delivery channel: '{channel}'."
