"""
Authentication Configuration Management Service (Phase 11).
Interacts directly with the existing `auth_configurations` database table.
Enforces strict server-side ownership isolation, validation of configuration JSON,
and guarantees that no secrets (passwords, OTPs, API keys) are ever persisted.
"""

import base64
import copy
import re
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from accounts.models import AuthConfigurations, AuthUser
from .template_registry import TemplateRegistry


class ConfigService:
    """
    CRUD service for AuthConfigurations with strict user-level ownership isolation.
    """

    FORBIDDEN_KEYS = (
        "password",
        "raw_password",
        "password_hash",
        "otp_code",
        "raw_otp",
        "otp_hash",
        "api_key",
        "secret",
        "token",
        "smtp_password",
        "twilio_token",
    )

    ALLOWED_SAFE_KEYS = (
        "otp_buttons",
        "default_otp",
        "enable_otp",
    )

    @classmethod
    def is_forbidden_key(cls, key: str) -> bool:
        k = str(key).lower().strip()
        if k in cls.ALLOWED_SAFE_KEYS:
            return False
        if k == "otp":
            return True
        return any(forbidden in k for forbidden in cls.FORBIDDEN_KEYS)

    @classmethod
    def validate_logo_data_uri(cls, logo_url: str, raise_exception: bool = False) -> str:
        """
        Validates uploaded logo data URI:
          - Enforces max 500 KB raw input (max ~685,000 base64 chars)
          - Restricts strictly to PNG, JPEG, and WebP MIME types
          - Strictly REJECTS SVG (prevents XSS, XML entity expansion)
          - Verifies binary magic bytes of the decoded image
        Returns the sanitized data URI or raises ValidationError if raise_exception is True.
        """
        from django.core.exceptions import ValidationError

        def _fail(msg):
            if raise_exception:
                raise ValidationError(msg)
            return ""

        if not logo_url or not isinstance(logo_url, str):
            return _fail("Empty or invalid logo data.")

        trimmed = logo_url.strip()
        if not trimmed:
            return _fail("Empty logo data.")

        # Reject SVG (both data URI and inline XML)
        if "<svg" in trimmed.lower() or "image/svg+xml" in trimmed.lower():
            return _fail("SVG logos are not allowed. Please upload PNG, JPEG, or WebP.")

        # Reject remote schemes that could cause SSRF or tracking leaks, or javascript: XSS
        if trimmed.lower().startswith(("javascript:", "vbscript:", "data:text/html", "data:text/javascript")):
            return _fail("Unsafe scheme in logo URI.")

        if trimmed.startswith("data:"):
            # Max 500 KB raw file -> ~683,000 base64 chars
            if len(trimmed) > 685000:
                return _fail("Logo image exceeds the 500 KB limit.")

            # Check MIME type prefix - strictly allow PNG, JPEG, WebP. Reject SVG!
            allowed_prefixes = (
                "data:image/png;base64,",
                "data:image/jpeg;base64,",
                "data:image/jpg;base64,",
                "data:image/webp;base64,",
            )
            matched_prefix = next((p for p in allowed_prefixes if trimmed.lower().startswith(p)), None)
            if not matched_prefix:
                return _fail("Corrupted or invalid image data. Only PNG, JPEG, and WebP are allowed.")

            # Extract base64 portion
            base64_data = trimmed[len(matched_prefix):]
            try:
                # Decode the first 64 bytes to inspect magic bytes
                decoded_header = base64.b64decode(base64_data[:128], validate=False)
                if matched_prefix == "data:image/png;base64,":
                    if not decoded_header.startswith(b"\x89PNG\r\n\x1a\n"):
                        return _fail("Corrupted or invalid PNG image magic bytes.")
                elif matched_prefix in ("data:image/jpeg;base64,", "data:image/jpg;base64,"):
                    if not decoded_header.startswith(b"\xff\xd8\xff"):
                        return _fail("Corrupted or invalid JPEG image magic bytes.")
                elif matched_prefix == "data:image/webp;base64,":
                    if not (decoded_header.startswith(b"RIFF") and len(decoded_header) >= 12 and decoded_header[8:12] == b"WEBP"):
                        return _fail("Corrupted or invalid WebP image magic bytes.")
            except Exception:
                return _fail("Corrupted or invalid base64 image data.")

            return trimmed

        # If it's a relative static path (e.g. /static/accounts/images/brand_logo.png), allow if safe
        if trimmed.startswith(("/static/", "/media/")):
            if re.match(r"^/[a-zA-Z0-9_\-./]+\.(png|jpg|jpeg|webp)$", trimmed, re.I):
                return trimmed
            return _fail("Invalid local path for logo.")

        return _fail("Unsupported logo URI format.")

    @classmethod
    def sanitize_branding(cls, branding: dict) -> dict:
        """Sanitizes and bounds branding configuration values."""
        clean_b = {}
        raw_name = branding.get("brand_name")
        if raw_name is None:
            clean_b["brand_name"] = "Auth Platform"
        else:
            clean_b["brand_name"] = str(raw_name).strip()[:60]
        clean_b["logo_url"] = cls.validate_logo_data_uri(branding.get("logo_url", ""), raise_exception=False)

        # Logo sizing
        width_str = str(branding.get("logo_width", "120px")).strip().lower()
        match_w = re.search(r"-?\d+", width_str)
        width_num = int(match_w.group(0)) if match_w else 120
        clean_b["logo_width"] = f"{max(30, min(240, width_num))}px"

        height_str = str(branding.get("logo_height", "36px")).strip().lower()
        match_h = re.search(r"-?\d+", height_str)
        height_num = int(match_h.group(0)) if match_h else 36
        clean_b["logo_height"] = f"{max(20, min(80, height_num))}px"

        try:
            scale_num = int(branding.get("logo_scale", 100))
            clean_b["logo_scale"] = max(50, min(150, scale_num))
        except (ValueError, TypeError):
            clean_b["logo_scale"] = 100

        align = str(branding.get("logo_align", "center")).strip().lower()
        clean_b["logo_align"] = align if align in ("left", "center", "right") else "center"

        clean_b["maintain_aspect_ratio"] = bool(branding.get("maintain_aspect_ratio", True))
        clean_b["favicon_url"] = str(branding.get("favicon_url", "")).strip()[:255]
        return clean_b

    @classmethod
    def sanitize_otp_buttons(cls, otp_btn: dict) -> dict:
        """Sanitizes and bounds OTP channel selector button values."""
        clean_o = {}
        mode = str(otp_btn.get("width_mode", "auto")).strip().lower()
        clean_o["width_mode"] = mode if mode in ("auto", "full", "custom") else "auto"

        cwidth_str = str(otp_btn.get("custom_width", "100px")).strip().lower()
        match_cw = re.search(r"-?\d+", cwidth_str)
        cwidth_num = int(match_cw.group(0)) if match_cw else 100
        clean_o["custom_width"] = f"{max(60, min(360, cwidth_num))}px"

        height_str = str(otp_btn.get("height", "38px")).strip().lower()
        match_h = re.search(r"-?\d+", height_str)
        height_num = int(match_h.group(0)) if match_h else 38
        clean_o["height"] = f"{max(32, min(54, height_num))}px"

        icon_str = str(otp_btn.get("icon_size", "16px")).strip().lower()
        match_ic = re.search(r"-?\d+", icon_str)
        icon_num = int(match_ic.group(0)) if match_ic else 16
        clean_o["icon_size"] = f"{max(12, min(24, icon_num))}px"

        font_str = str(otp_btn.get("font_size", "12px")).strip().lower()
        match_fn = re.search(r"-?\d+", font_str)
        font_num = int(match_fn.group(0)) if match_fn else 12
        clean_o["font_size"] = f"{max(10, min(18, font_num))}px"

        radius_str = str(otp_btn.get("radius", "6px")).strip().lower()
        match_rd = re.search(r"-?\d+", radius_str)
        radius_num = int(match_rd.group(0)) if match_rd else 6
        clean_o["radius"] = f"{max(0, min(32, radius_num))}px"

        gap_str = str(otp_btn.get("gap", "8px")).strip().lower()
        match_gp = re.search(r"-?\d+", gap_str)
        gap_num = int(match_gp.group(0)) if match_gp else 8
        clean_o["gap"] = f"{max(2, min(20, gap_num))}px"

        clean_o["padding"] = str(otp_btn.get("padding", "6px 14px")).strip()[:30]
        bw = str(otp_btn.get("border_width", "1px")).strip().lower()
        match_bw = re.search(r"-?\d+", bw)
        bw_num = int(match_bw.group(0)) if match_bw else 1
        clean_o["border_width"] = f"{max(0, min(4, bw_num))}px"

        return clean_o

    @classmethod
    def sanitize_config_data(cls, raw_data: dict) -> dict:
        """
        Recursively strips forbidden sensitive keys and sanitizes values.
        Provides safe defaults for branding and otp_buttons if missing in legacy configs.
        """
        if not isinstance(raw_data, dict):
            return {}

        clean = {}
        for k, v in raw_data.items():
            if cls.is_forbidden_key(k):
                continue
            if isinstance(v, dict):
                clean[k] = cls.sanitize_config_data(v)
            elif isinstance(v, list):
                clean[k] = [cls.sanitize_config_data(item) if isinstance(item, dict) else item for item in v]
            elif isinstance(v, str):
                # Basic HTML tag escaping to prevent injection
                clean[k] = v.replace("<script", "&lt;script").replace("</script", "&lt;/script")
            else:
                clean[k] = v

        if "branding" in clean and isinstance(clean["branding"], dict):
            clean["branding"] = cls.sanitize_branding(clean["branding"])
        elif "template" in clean or "template_id" in clean:
            clean["branding"] = cls.sanitize_branding({})

        if "otp_buttons" in clean and isinstance(clean["otp_buttons"], dict):
            clean["otp_buttons"] = cls.sanitize_otp_buttons(clean["otp_buttons"])
        elif "template" in clean or "template_id" in clean:
            clean["otp_buttons"] = cls.sanitize_otp_buttons({})

        return clean

    @classmethod
    def list_configurations(cls, user: AuthUser | None, session_id: str | None = None):
        """
        Lists configurations owned by the user. If anonymous, filters by builder_session_id.
        User A cannot view User B's configurations.
        """
        if user and getattr(user, "is_authenticated", False):
            return AuthConfigurations.objects.filter(user=user).order_by("-updated_at")
        elif session_id:
            return AuthConfigurations.objects.filter(builder_session_id=session_id, user__isnull=True).order_by("-updated_at")
        return AuthConfigurations.objects.none()

    @classmethod
    def get_configuration(cls, config_id: int, user: AuthUser | None, session_id: str | None = None) -> AuthConfigurations:
        """
        Retrieves a configuration record enforcing strict ownership authorization.
        Raises PermissionDenied if the requesting user is not the owner.
        """
        config = AuthConfigurations.objects.filter(pk=config_id).first()
        if not config:
            raise AuthConfigurations.DoesNotExist(f"Configuration #{config_id} does not exist.")

        # Ownership verification
        if user and getattr(user, "is_authenticated", False):
            if config.user_id != user.id:
                raise PermissionDenied("You do not have permission to access this configuration.")
        else:
            if not session_id or config.builder_session_id != session_id:
                raise PermissionDenied("You do not have permission to access this configuration.")

        return config

    @classmethod
    def save_configuration(
        cls,
        name: str,
        data: dict,
        user: AuthUser | None,
        config_id: int | None = None,
        session_id: str | None = None,
        landing_url: str = "",
        redirect_url: str = "",
    ) -> AuthConfigurations:
        """
        Saves or updates a configuration. Enforces ownership and sanitizes data.
        """
        clean_name = (name or "Untitled Configuration").strip()[:255]
        clean_data = cls.sanitize_config_data(data)

        if config_id:
            config = cls.get_configuration(config_id, user, session_id)
            config.configuration_name = clean_name
            config.configuration_data = clean_data
            if landing_url:
                config.landing_url = landing_url
            if redirect_url:
                config.redirect_url = redirect_url
            config.updated_at = timezone.now()
            config.save()
            return config

        # Create new
        new_config = AuthConfigurations.objects.create(
            user=user if user and getattr(user, "is_authenticated", False) else None,
            builder_session_id=session_id if (not user or not getattr(user, "is_authenticated", False)) else None,
            configuration_name=clean_name,
            configuration_data=clean_data,
            landing_url=landing_url,
            redirect_url=redirect_url,
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return new_config

    @classmethod
    def rename_configuration(
        cls,
        config_id: int,
        new_name: str,
        user: AuthUser | None,
        session_id: str | None = None,
    ) -> AuthConfigurations:
        config = cls.get_configuration(config_id, user, session_id)
        config.configuration_name = (new_name or "Untitled Configuration").strip()[:255]
        config.updated_at = timezone.now()
        config.save()
        return config

    @classmethod
    def duplicate_configuration(
        cls,
        config_id: int,
        user: AuthUser | None,
        session_id: str | None = None,
    ) -> AuthConfigurations:
        config = cls.get_configuration(config_id, user, session_id)
        clone = AuthConfigurations.objects.create(
            user=config.user,
            builder_session_id=config.builder_session_id,
            configuration_name=f"{config.configuration_name} (Copy)"[:255],
            configuration_data=copy.deepcopy(config.configuration_data),
            landing_url=config.landing_url,
            redirect_url=config.redirect_url,
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return clone

    @classmethod
    def delete_configuration(
        cls,
        config_id: int,
        user: AuthUser | None,
        session_id: str | None = None,
    ) -> bool:
        config = cls.get_configuration(config_id, user, session_id)
        config.delete()
        return True

    @classmethod
    def activate_configuration(
        cls,
        config_id: int,
        user: AuthUser | None,
        session_id: str | None = None,
    ) -> AuthConfigurations:
        config = cls.get_configuration(config_id, user, session_id)
        # Deactivate other configurations for this user/session
        if user and getattr(user, "is_authenticated", False):
            AuthConfigurations.objects.filter(user=user).exclude(pk=config_id).update(is_active=0)
        elif session_id:
            AuthConfigurations.objects.filter(builder_session_id=session_id).exclude(pk=config_id).update(is_active=0)

        config.is_active = 1
        config.updated_at = timezone.now()
        config.save()
        return config
