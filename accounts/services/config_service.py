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
    def validate_background_data_uri(cls, bg_url: str, raise_exception: bool = False) -> str:
        """
        Validates uploaded background data URI:
          - Enforces max 1.5 MB raw input (max ~2,100,000 base64 chars)
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

        if not bg_url or not isinstance(bg_url, str):
            return _fail("Empty or invalid background data.")

        trimmed = bg_url.strip()
        if not trimmed:
            return _fail("Empty background data.")

        # Reject SVG (both data URI and inline XML)
        if "<svg" in trimmed.lower() or "image/svg+xml" in trimmed.lower():
            return _fail("SVG background images are not allowed. Please upload PNG, JPEG, or WebP.")

        # Reject remote schemes that could cause SSRF or tracking leaks, or javascript: XSS
        if trimmed.lower().startswith(("javascript:", "vbscript:", "data:text/html", "data:text/javascript")):
            return _fail("Unsafe scheme in background image URI.")

        if trimmed.startswith("data:"):
            # Max 1.5 MB raw file -> ~2,050,000 base64 chars
            if len(trimmed) > 2100000:
                return _fail("Background image exceeds the 1.5 MB limit.")

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

        # Allow direct HTTP/HTTPS image URLs
        if trimmed.lower().startswith(("http://", "https://")):
            if len(trimmed) > 2048:
                return _fail("Background image URL exceeds the 2048 characters limit.")
            # Disallow control chars or quotes that could break CSS/HTML attributes
            if any(c in trimmed for c in ('"', "'", "<", ">", ";", "\n", "\r", "\\")):
                return _fail("Background image URL contains unsafe characters.")
            return trimmed

        # If it's a relative static path (e.g. /static/accounts/images/background.png), allow if safe
        if trimmed.startswith(("/static/", "/media/")):
            if re.match(r"^/[a-zA-Z0-9_\-./]+\.(png|jpg|jpeg|webp)$", trimmed, re.I):
                return trimmed
            return _fail("Invalid local path for background image.")

        return _fail("Unsupported background image URI format.")

    @classmethod
    def sanitize_background(cls, bg: dict) -> dict:
        """Sanitizes and bounds background configuration values."""
        clean = {}
        b_type = str(bg.get("type", "color")).strip().lower()
        clean["type"] = b_type if b_type in ("color", "gradient", "image") else "color"

        # Background color
        raw_color = str(bg.get("color", "#131315")).strip()
        clean["color"] = raw_color[:30] if raw_color else "#131315"

        # Gradient
        grad = bg.get("gradient", {})
        if not isinstance(grad, dict):
            grad = {}
        raw_angle = grad.get("angle", 135)
        try:
            if isinstance(raw_angle, (int, float)):
                clean_angle = int(raw_angle) % 360
            else:
                m = re.search(r"-?\d+", str(raw_angle))
                clean_angle = int(m.group(0)) % 360 if m else 135
        except Exception:
            clean_angle = 135

        g_type = str(grad.get("type", "linear")).strip().lower()
        clean_grad = {
            "type": g_type if g_type in ("linear", "radial") else "linear",
            "start_color": str(grad.get("start_color", clean["color"])).strip()[:30],
            "end_color": str(grad.get("end_color", "#201f22")).strip()[:30],
            "angle": clean_angle,
        }
        clean["gradient"] = clean_grad

        # Image URL and Source (upload vs url)
        raw_img = bg.get("image_url", "")
        clean["image_url"] = cls.validate_background_data_uri(raw_img, raise_exception=False) if raw_img else ""
        raw_src = str(bg.get("source", "")).strip().lower()
        if raw_src in ("upload", "url"):
            clean["source"] = raw_src
        else:
            clean["source"] = "url" if (clean["image_url"] and clean["image_url"].startswith(("http://", "https://"))) else "upload"

        # Position
        pos = str(bg.get("position", "center")).strip().lower()
        valid_bg_positions = (
            "center", "top", "bottom", "left", "right",
            "top-left", "top-right", "bottom-left", "bottom-right",
            "top left", "top right", "bottom left", "bottom right"
        )
        clean["position"] = pos if pos in valid_bg_positions else "center"

        # Size
        size = str(bg.get("size", "cover")).strip().lower()
        clean["size"] = size if size in ("cover", "contain", "auto") else "cover"

        # Repeat
        rep = str(bg.get("repeat", "no-repeat")).strip().lower()
        clean["repeat"] = rep if rep in ("no-repeat", "repeat", "repeat-x", "repeat-y") else "no-repeat"

        # Overlay
        overlay = bg.get("overlay", {})
        if not isinstance(overlay, dict):
            overlay = {}
        try:
            op_val = int(overlay.get("opacity", 0))
            op_val = max(0, min(100, op_val))
        except (ValueError, TypeError):
            op_val = 0
        clean["overlay"] = {
            "color": str(overlay.get("color", "#000000")).strip()[:30],
            "opacity": op_val,
        }

        # Effects
        try:
            blur_val = int(bg.get("blur", 0))
            clean["blur"] = max(0, min(20, blur_val))
        except (ValueError, TypeError):
            clean["blur"] = 0

        try:
            bright_val = int(bg.get("brightness", 100))
            clean["brightness"] = max(50, min(150, bright_val))
        except (ValueError, TypeError):
            clean["brightness"] = 100

        try:
            sat_val = int(bg.get("saturation", 100))
            clean["saturation"] = max(0, min(200, sat_val))
        except (ValueError, TypeError):
            clean["saturation"] = 100

        return clean

    @classmethod
    def sanitize_card(cls, card: dict) -> dict:
        """Sanitizes and bounds card styling configuration values."""
        clean = {}

        # Width
        w_str = str(card.get("width", "420px")).strip().lower()
        m_w = re.search(r"-?\d+", w_str)
        w_num = int(m_w.group(0)) if m_w else 420
        clean["width"] = f"{max(320, min(600, w_num))}px"

        clean["max_width"] = str(card.get("max_width", "100%")).strip()[:20]

        # Padding
        p_str = str(card.get("padding", "2rem")).strip().lower()
        m_p = re.search(r"-?\d+", p_str)
        p_num = int(m_p.group(0)) if m_p else 32
        if "rem" in p_str:
            clean["padding"] = p_str[:15]
        else:
            clean["padding"] = f"{max(16, min(48, p_num))}px"

        # Background color
        clean["background_color"] = str(card.get("background_color") or card.get("card_bg") or "#201f22").strip()[:30]

        # Opacity
        try:
            op = int(card.get("opacity", 100))
            clean["opacity"] = max(0, min(100, op))
        except (ValueError, TypeError):
            clean["opacity"] = 100

        # Radius / Border Radius
        r_str = str(card.get("border_radius") or card.get("radius", "12px")).strip().lower()
        m_r = re.search(r"-?\d+", r_str)
        r_num = int(m_r.group(0)) if m_r else 12
        rad_val = f"{max(0, min(32, r_num))}px"
        clean["radius"] = rad_val
        clean["border_radius"] = rad_val

        # Appearance (opaque, translucent, glass)
        app = str(card.get("appearance") or ("glass" if card.get("preset") == "glass" else "opaque")).strip().lower()
        clean["appearance"] = app if app in ("opaque", "translucent", "glass") else "opaque"

        # Border enabled & opacity
        b_en = card.get("border_enabled", True)
        if isinstance(b_en, str):
            clean["border_enabled"] = b_en.lower() not in ("false", "0", "no", "off")
        else:
            clean["border_enabled"] = bool(b_en)

        try:
            b_op = int(card.get("border_opacity", 30 if clean["appearance"] in ("glass", "translucent") else 100))
            clean["border_opacity"] = max(0, min(100, b_op))
        except (ValueError, TypeError):
            clean["border_opacity"] = 30

        # Border width
        bw_val = card.get("border_width", 1)
        bw_str = str(bw_val).strip().lower()
        m_bw = re.search(r"-?\d+", bw_str)
        bw_num = int(m_bw.group(0)) if m_bw else 1
        clean["border_width"] = max(0, min(4, bw_num)) if isinstance(bw_val, int) else f"{max(0, min(4, bw_num))}px"

        # Border color
        clean["border_color"] = str(card.get("border_color", "rgba(76, 69, 70, 0.35)")).strip()[:40]

        # Shadow
        shadow_val = card.get("shadow", "medium" if clean["appearance"] == "glass" else "subtle")
        if str(shadow_val).lower() in ("none", "subtle", "medium", "strong"):
            clean["shadow"] = str(shadow_val).lower()
        elif isinstance(shadow_val, str) and ("rgba" in shadow_val or "px" in shadow_val):
            clean["shadow"] = shadow_val[:120]
        else:
            clean["shadow"] = "medium" if clean["appearance"] == "glass" else "subtle"

        sb_str = str(card.get("shadow_blur", "40px")).strip().lower()
        m_sb = re.search(r"-?\d+", sb_str)
        sb_num = int(m_sb.group(0)) if m_sb else 40
        clean["shadow_blur"] = f"{max(0, min(50, sb_num))}px"

        sp_str = str(card.get("shadow_spread", "0px")).strip().lower()
        m_sp = re.search(r"-?\d+", sp_str)
        sp_num = int(m_sp.group(0)) if m_sp else 0
        clean["shadow_spread"] = f"{max(-10, min(20, sp_num))}px"

        # Blur & Backdrop Blur
        b_blur_raw = card.get("backdrop_blur") if card.get("backdrop_blur") is not None else card.get("blur")
        try:
            m_b = re.search(r"-?\d+", str(b_blur_raw))
            b_num = int(m_b.group(0)) if m_b else (14 if clean["appearance"] == "glass" else 0)
        except Exception:
            b_num = 14 if clean["appearance"] == "glass" else 0
        clean_blur = max(0, min(30, b_num))
        clean["blur"] = clean_blur
        clean["backdrop_blur"] = clean_blur

        # Alignment
        align = str(card.get("alignment", "center")).strip().lower()
        clean["alignment"] = align if align in ("left", "center", "right") else "center"

        # Position Anchor & Coordinates
        valid_positions = (
            "center", "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right",
            "top left", "top center", "top right",
            "center left", "center right",
            "bottom left", "bottom center", "bottom right"
        )
        pos = str(card.get("position", "center")).strip().lower()
        clean["position"] = pos if pos in valid_positions else "center"

        try:
            h_pos = int(card.get("horizontal_position", 50))
            clean["horizontal_position"] = max(0, min(100, h_pos))
        except (ValueError, TypeError):
            clean["horizontal_position"] = 50

        try:
            v_pos = int(card.get("vertical_position", 50))
            clean["vertical_position"] = max(0, min(100, v_pos))
        except (ValueError, TypeError):
            clean["vertical_position"] = 50

        # Preset
        c_preset = str(card.get("preset", "default")).strip().lower()
        clean["preset"] = c_preset if c_preset in ("default", "minimal", "soft", "elevated", "glass", "bordered") else "default"

        return clean

    @classmethod
    def sanitize_animations(cls, anim: dict) -> dict:
        """Sanitizes and bounds card entrance animations."""
        clean = {}
        raw_type = str(anim.get("type", "fade")).strip().lower()
        if raw_type in ("none", "fade", "slide_up", "slide-up", "slide_down", "slide-down", "scale", "float", "subtle_float", "subtle-float"):
            clean["type"] = "slide_up" if raw_type in ("slide_up", "slide-up") else ("slide_down" if raw_type in ("slide_down", "slide-down") else ("float" if raw_type in ("float", "subtle_float", "subtle-float") else raw_type))
        else:
            clean["type"] = "fade"

        d_val = anim.get("duration", 250)
        d_str = str(d_val).strip().lower()
        m_d = re.search(r"-?\d+", d_str)
        d_num = int(m_d.group(0)) if m_d else 250
        clean["duration"] = max(100, min(800, d_num))

        dl_val = anim.get("delay", 0)
        dl_str = str(dl_val).strip().lower()
        m_dl = re.search(r"-?\d+", dl_str)
        dl_num = int(m_dl.group(0)) if m_dl else 0
        clean["delay"] = max(0, min(500, dl_num))

        intensity = str(anim.get("intensity", "subtle")).strip().lower()
        clean["intensity"] = intensity if intensity in ("subtle", "normal") else "subtle"
        return clean

    @classmethod
    def sanitize_otp_buttons(cls, otp: dict) -> dict:
        """Sanitizes and bounds OTP selector button dimensions and typography."""
        clean = {}
        w_mode = str(otp.get("width_mode", "auto")).strip().lower()
        clean["width_mode"] = w_mode if w_mode in ("auto", "full", "custom") else "auto"

        cw_str = str(otp.get("custom_width", "100px")).strip().lower()
        m_cw = re.search(r"-?\d+", cw_str)
        cw_num = int(m_cw.group(0)) if m_cw else 100
        clean["custom_width"] = f"{max(50, min(360, cw_num))}px"

        h_str = str(otp.get("height", "38px")).strip().lower()
        m_h = re.search(r"-?\d+", h_str)
        h_num = int(m_h.group(0)) if m_h else 38
        clean["height"] = f"{max(32, min(64, h_num))}px"

        r_str = str(otp.get("radius", "6px")).strip().lower()
        m_r = re.search(r"-?\d+", r_str)
        r_num = int(m_r.group(0)) if m_r else 6
        clean["radius"] = f"{max(0, min(32, r_num))}px"

        g_str = str(otp.get("gap", "8px")).strip().lower()
        m_g = re.search(r"-?\d+", g_str)
        g_num = int(m_g.group(0)) if m_g else 8
        clean["gap"] = f"{max(2, min(24, g_num))}px"

        clean["padding"] = str(otp.get("padding", "6px 14px")).strip()[:30]

        fs_str = str(otp.get("font_size", "12px")).strip().lower()
        m_fs = re.search(r"-?\d+", fs_str)
        fs_num = int(m_fs.group(0)) if m_fs else 12
        clean["font_size"] = f"{max(10, min(18, fs_num))}px"

        is_str = str(otp.get("icon_size", "16px")).strip().lower()
        m_is = re.search(r"-?\d+", is_str)
        is_num = int(m_is.group(0)) if m_is else 16
        clean["icon_size"] = f"{max(12, min(28, is_num))}px"

        bw_str = str(otp.get("border_width", "1px")).strip().lower()
        m_bw = re.search(r"-?\d+", bw_str)
        bw_num = int(m_bw.group(0)) if m_bw else 1
        clean["border_width"] = f"{max(0, min(4, bw_num))}px"

        return clean

    @classmethod
    def sanitize_theme(cls, theme: dict) -> dict:
        """Sanitizes theme mode ensuring it is strictly dark, light, or system."""
        if not isinstance(theme, dict):
            return {"mode": "dark"}
        mode = str(theme.get("mode", "dark")).strip().lower()
        return {"mode": mode if mode in ("dark", "light", "system") else "dark"}

    @classmethod
    def sanitize_palette(cls, palette: dict) -> dict:
        """Sanitizes color palette selection and optional overrides."""
        clean = {}
        if not isinstance(palette, dict):
            return {"preset": "indigo"}
        p_name = str(palette.get("preset", "indigo")).strip().lower()
        clean["preset"] = p_name if p_name in TemplateRegistry.COLOR_PALETTES else "indigo"
        if "custom_colors" in palette and isinstance(palette["custom_colors"], dict):
            clean_custom = {}
            for k, val in palette["custom_colors"].items():
                if isinstance(val, str) and len(val) <= 40:
                    clean_custom[str(k)[:30]] = val.strip()
            clean["custom_colors"] = clean_custom
        return clean

    @classmethod
    def sanitize_spacing(cls, spacing: dict) -> dict:
        """Sanitizes spacing and density settings."""
        clean = {}
        if not isinstance(spacing, dict):
            return {"density": "comfortable"}
        density = str(spacing.get("density", "comfortable")).strip().lower()
        clean["density"] = density if density in ("compact", "comfortable", "spacious") else "comfortable"
        return clean

    @classmethod
    def sanitize_buttons(cls, buttons: dict) -> dict:
        """Sanitizes button presets and style overrides."""
        clean = {}
        if not isinstance(buttons, dict):
            return {"preset": "solid"}
        preset = str(buttons.get("preset", "solid")).strip().lower()
        clean["preset"] = preset if preset in ("solid", "soft", "outline", "ghost", "gradient", "pill", "sharp") else "solid"
        if "border_radius" in buttons:
            r_str = str(buttons["border_radius"]).strip().lower()
            m = re.search(r"-?\d+", r_str)
            clean["border_radius"] = f"{max(0, min(32, int(m.group(0))))}px" if m else "8px"
        if "primary_color" in buttons:
            clean["primary_color"] = str(buttons["primary_color"]).strip()[:30]
        if "text_color" in buttons:
            clean["text_color"] = str(buttons["text_color"]).strip()[:30]
        return clean

    @classmethod
    def sanitize_inputs(cls, inputs: dict) -> dict:
        """Sanitizes input presets and style overrides."""
        clean = {}
        if not isinstance(inputs, dict):
            return {"preset": "minimal"}
        preset = str(inputs.get("preset", "minimal")).strip().lower()
        clean["preset"] = preset if preset in ("minimal", "bordered", "filled", "soft", "glass") else "minimal"
        if "border_radius" in inputs:
            r_str = str(inputs["border_radius"]).strip().lower()
            m = re.search(r"-?\d+", r_str)
            clean["border_radius"] = f"{max(0, min(32, int(m.group(0))))}px" if m else "8px"
        if "bg_color" in inputs:
            clean["bg_color"] = str(inputs["bg_color"]).strip()[:30]
        if "border_color" in inputs:
            clean["border_color"] = str(inputs["border_color"]).strip()[:30]
        return clean

    @classmethod
    def sanitize_layout(cls, layout: dict) -> dict:
        """Sanitizes layout structure and card positioning coordinates."""
        clean = {}
        if not isinstance(layout, dict):
            layout = {}

        style = str(layout.get("style", "centered")).strip().lower()
        clean["style"] = style if style in ("centered", "split", "left", "right") else "centered"
        clean["background_type"] = str(layout.get("background_type", "gradient")).strip()[:30]

        valid_positions = (
            "center", "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right",
            "top left", "top center", "top right",
            "center left", "center right",
            "bottom left", "bottom center", "bottom right"
        )
        pos = str(layout.get("card_position", "center")).strip().lower()
        clean["card_position"] = pos if pos in valid_positions else "center"

        try:
            h_pos = int(layout.get("card_horizontal_position", 50))
            clean["card_horizontal_position"] = max(0, min(100, h_pos))
        except (ValueError, TypeError):
            clean["card_horizontal_position"] = 50

        try:
            v_pos = int(layout.get("card_vertical_position", 50))
            clean["card_vertical_position"] = max(0, min(100, v_pos))
        except (ValueError, TypeError):
            clean["card_vertical_position"] = 50

        return clean

    @classmethod
    def sanitize_config_data(cls, raw_data: dict) -> dict:
        """
        Recursively strips forbidden sensitive keys and sanitizes values.
        Provides safe defaults for branding, background, card, animations, theme, and otp_buttons.
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

        if "theme" in clean and isinstance(clean["theme"], dict):
            clean["theme"] = cls.sanitize_theme(clean["theme"])
        else:
            clean["theme"] = {"mode": "dark"}

        if "palette" in clean and isinstance(clean["palette"], dict):
            clean["palette"] = cls.sanitize_palette(clean["palette"])

        if "design_preset" in clean:
            dp = str(clean["design_preset"]).strip().lower()
            valid_presets = set(TemplateRegistry.DESIGN_PRESETS.keys()) | {k.replace("-", "_") for k in TemplateRegistry.DESIGN_PRESETS.keys()}
            clean["design_preset"] = dp if dp in valid_presets else ""

        if "spacing" in clean and isinstance(clean["spacing"], dict):
            clean["spacing"] = cls.sanitize_spacing(clean["spacing"])

        if "buttons" in clean and isinstance(clean["buttons"], dict):
            clean["buttons"] = cls.sanitize_buttons(clean["buttons"])

        if "inputs" in clean and isinstance(clean["inputs"], dict):
            clean["inputs"] = cls.sanitize_inputs(clean["inputs"])

        if "branding" in clean and isinstance(clean["branding"], dict):
            clean["branding"] = cls.sanitize_branding(clean["branding"])
        elif "template" in clean or "template_id" in clean:
            clean["branding"] = cls.sanitize_branding({})

        if "background" in clean and isinstance(clean["background"], dict):
            clean["background"] = cls.sanitize_background(clean["background"])

        if "card" in clean and isinstance(clean["card"], dict):
            clean["card"] = cls.sanitize_card(clean["card"])

        if "animations" in clean and isinstance(clean["animations"], dict):
            clean["animations"] = cls.sanitize_animations(clean["animations"])

        if "layout" in clean and isinstance(clean["layout"], dict):
            clean["layout"] = cls.sanitize_layout(clean["layout"])

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


# Module-level convenience aliases
sanitize_config_data = ConfigService.sanitize_config_data
validate_background_data_uri = ConfigService.validate_background_data_uri
validate_logo_data_uri = ConfigService.validate_logo_data_uri
