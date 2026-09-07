"""
Template Registry & Dynamic Design Token System (Phases 8 & 9).
Provides a centralized registry of authentication visual templates, default configuration
schemas, and utility to generate dynamic CSS root variables for live customization in the builder.
"""

import copy

class TemplateRegistry:
    TEMPLATES = {
        "modern": {
            "id": "modern",
            "name": "Modern Glass",
            "description": "Luxurious frosted glassmorphism with glowing neon gradients, dark aesthetic, and vibrant accents.",
            "badge": "Dark / Glassmorphism",
            "dir": "accounts/templates/modern",
            "css": "accounts/css/template_modern.css",
            "defaults": {
                "template": "modern",
                "branding": {
                    "brand_name": "Auth Platform",
                    "logo_url": "",
                    "logo_width": "120px",
                    "logo_height": "36px",
                    "logo_scale": 100,
                    "logo_align": "center",
                    "maintain_aspect_ratio": True,
                    "favicon_url": "",
                },
                "colors": {
                    "primary": "#6366f1",
                    "primary_hover": "#4f46e5",
                    "secondary": "#06b6d4",
                    "background": "#090d16",
                    "card_bg": "rgba(17, 24, 39, 0.72)",
                    "text": "#f8fafc",
                    "muted": "#94a3b8",
                    "border": "rgba(255, 255, 255, 0.12)",
                    "btn_bg": "#6366f1",
                    "btn_text": "#ffffff",
                    "error": "#ef4444",
                    "success": "#10b981",
                },
                "typography": {
                    "font_family": "Inter, -apple-system, sans-serif",
                    "heading_size": "1.75rem",
                    "body_size": "0.925rem",
                    "label_size": "0.85rem",
                    "font_weight": "600",
                    "letter_spacing": "-0.025em",
                },
                "card": {
                    "width": "460px",
                    "padding": "2rem",
                    "radius": "16px",
                    "border_width": "1px",
                    "blur": "20px",
                    "shadow": "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
                },
                "inputs": {
                    "height": "44px",
                    "radius": "8px",
                    "bg": "rgba(15, 23, 42, 0.7)",
                    "border": "rgba(255, 255, 255, 0.12)",
                },
                "buttons": {
                    "height": "46px",
                    "radius": "8px",
                    "font_weight": "600",
                },
                "otp_buttons": {
                    "width_mode": "auto",
                    "custom_width": "100px",
                    "height": "38px",
                    "icon_size": "16px",
                    "font_size": "12px",
                    "radius": "6px",
                    "gap": "8px",
                    "padding": "6px 14px",
                    "border_width": "1px",
                },
                "layout": {
                    "style": "centered",
                    "background_type": "gradient",
                },
                "authentication": {
                    "enable_password": True,
                    "enable_otp": True,
                    "enable_email": True,
                    "enable_sms": True,
                    "enable_whatsapp": True,
                    "default_otp": "email",
                    "remember_me": True,
                    "show_register": True,
                    "show_forgot": True,
                },
                "responsive": {
                    "mobile_width": "100%",
                    "mobile_padding": "1rem",
                },
            },
        },
        "split": {
            "id": "split",
            "name": "Split Screen",
            "description": "High-converting editorial SaaS layout with branding hero showcase and focused auth card.",
            "badge": "2-Column / SaaS",
            "dir": "accounts/templates/split",
            "css": "accounts/css/template_split.css",
            "defaults": {
                "template": "split",
                "branding": {
                    "brand_name": "Auth Platform",
                    "hero_title": "Authentication Built for Modern Scale.",
                    "hero_subtitle": "Unified multi-factor identity, multi-channel OTP delivery across Email, SMS, and WhatsApp, and instant session invalidation.",
                    "logo_url": "",
                    "logo_width": "120px",
                    "logo_height": "36px",
                    "logo_scale": 100,
                    "logo_align": "left",
                    "maintain_aspect_ratio": True,
                    "favicon_url": "",
                },
                "colors": {
                    "primary": "#2563eb",
                    "primary_hover": "#1d4ed8",
                    "secondary": "#38bdf8",
                    "background": "#f8fafc",
                    "card_bg": "#ffffff",
                    "text": "#0f172a",
                    "muted": "#64748b",
                    "border": "#e2e8f0",
                    "btn_bg": "#2563eb",
                    "btn_text": "#ffffff",
                    "error": "#ef4444",
                    "success": "#10b981",
                },
                "typography": {
                    "font_family": "Inter, -apple-system, sans-serif",
                    "heading_size": "1.65rem",
                    "body_size": "0.9rem",
                    "label_size": "0.85rem",
                    "font_weight": "600",
                    "letter_spacing": "-0.025em",
                },
                "card": {
                    "width": "460px",
                    "padding": "2rem",
                    "radius": "16px",
                    "border_width": "1px",
                    "blur": "0px",
                    "shadow": "0 10px 25px -5px rgba(0, 0, 0, 0.05)",
                },
                "inputs": {
                    "height": "44px",
                    "radius": "8px",
                    "bg": "#ffffff",
                    "border": "#cbd5e1",
                },
                "buttons": {
                    "height": "46px",
                    "radius": "8px",
                    "font_weight": "600",
                },
                "otp_buttons": {
                    "width_mode": "auto",
                    "custom_width": "100px",
                    "height": "38px",
                    "icon_size": "16px",
                    "font_size": "12px",
                    "radius": "6px",
                    "gap": "8px",
                    "padding": "6px 14px",
                    "border_width": "1px",
                },
                "layout": {
                    "style": "split",
                    "background_type": "split",
                },
                "authentication": {
                    "enable_password": True,
                    "enable_otp": True,
                    "enable_email": True,
                    "enable_sms": True,
                    "enable_whatsapp": True,
                    "default_otp": "email",
                    "remember_me": True,
                    "show_register": True,
                    "show_forgot": True,
                },
                "responsive": {
                    "mobile_width": "100%",
                    "mobile_padding": "1.25rem",
                },
            },
        },
        "corporate": {
            "id": "corporate",
            "name": "Minimal Corporate",
            "description": "Clean, ultra-crisp, enterprise light aesthetic with high legibility and refined focus states.",
            "badge": "Light / Enterprise",
            "dir": "accounts/templates/corporate",
            "css": "accounts/css/template_corporate.css",
            "defaults": {
                "template": "corporate",
                "branding": {
                    "brand_name": "Auth Platform",
                    "logo_url": "",
                    "logo_width": "120px",
                    "logo_height": "36px",
                    "logo_scale": 100,
                    "logo_align": "center",
                    "maintain_aspect_ratio": True,
                    "favicon_url": "",
                },
                "colors": {
                    "primary": "#0f172a",
                    "primary_hover": "#1e293b",
                    "secondary": "#475569",
                    "background": "#f8fafc",
                    "card_bg": "#ffffff",
                    "text": "#0f172a",
                    "muted": "#64748b",
                    "border": "#e2e8f0",
                    "btn_bg": "#0f172a",
                    "btn_text": "#ffffff",
                    "error": "#ef4444",
                    "success": "#10b981",
                },
                "typography": {
                    "font_family": "Inter, -apple-system, sans-serif",
                    "heading_size": "1.5rem",
                    "body_size": "0.875rem",
                    "label_size": "0.825rem",
                    "font_weight": "600",
                    "letter_spacing": "-0.02em",
                },
                "card": {
                    "width": "440px",
                    "padding": "2rem",
                    "radius": "10px",
                    "border_width": "1px",
                    "blur": "0px",
                    "shadow": "0 1px 3px rgba(0, 0, 0, 0.06)",
                },
                "inputs": {
                    "height": "42px",
                    "radius": "6px",
                    "bg": "#ffffff",
                    "border": "#cbd5e1",
                },
                "buttons": {
                    "height": "44px",
                    "radius": "6px",
                    "font_weight": "600",
                },
                "otp_buttons": {
                    "width_mode": "auto",
                    "custom_width": "100px",
                    "height": "38px",
                    "icon_size": "16px",
                    "font_size": "12px",
                    "radius": "6px",
                    "gap": "8px",
                    "padding": "6px 14px",
                    "border_width": "1px",
                },
                "layout": {
                    "style": "centered",
                    "background_type": "grid",
                },
                "authentication": {
                    "enable_password": True,
                    "enable_otp": True,
                    "enable_email": True,
                    "enable_sms": True,
                    "enable_whatsapp": True,
                    "default_otp": "email",
                    "remember_me": True,
                    "show_register": True,
                    "show_forgot": True,
                },
                "responsive": {
                    "mobile_width": "100%",
                    "mobile_padding": "1rem",
                },
            },
        },
    }

    @classmethod
    def get_all(cls):
        return cls.TEMPLATES

    @classmethod
    def get(cls, template_id: str):
        key = (template_id or "modern").strip().lower()
        return cls.TEMPLATES.get(key, cls.TEMPLATES["modern"])

    @classmethod
    def get_default_config(cls, template_id: str) -> dict:
        tpl = cls.get(template_id)
        return copy.deepcopy(tpl["defaults"])

    @classmethod
    def get_default_configuration(cls, template_id: str) -> dict:
        return cls.get_default_config(template_id)

    @classmethod
    def merge_config(cls, template_id: str, custom_config: dict | None) -> dict:
        config = cls.get_default_config(template_id)
        if not custom_config or not isinstance(custom_config, dict):
            return config

        for section, values in custom_config.items():
            if section in config and isinstance(values, dict) and isinstance(config[section], dict):
                config[section].update(values)
            else:
                config[section] = values
        return config

    @classmethod
    def generate_css_variables(cls, config: dict) -> str:
        """Converts a configuration dict into CSS custom property declarations for :root."""
        colors = config.get("colors", {})
        card = config.get("card", {})
        inputs = config.get("inputs", {})
        buttons = config.get("buttons", {})
        typography = config.get("typography", {})
        branding = config.get("branding", {})
        otp_buttons = config.get("otp_buttons", {})

        vars_list = []
        if colors.get("primary"):
            vars_list.append(f"--primary-color: {colors['primary']};")
        if colors.get("primary_hover"):
            vars_list.append(f"--primary-hover: {colors['primary_hover']};")
        if colors.get("secondary"):
            vars_list.append(f"--secondary-color: {colors['secondary']};")
        if colors.get("background"):
            vars_list.append(f"--background-color: {colors['background']};")
        if colors.get("card_bg"):
            vars_list.append(f"--card-background: {colors['card_bg']};")
        if colors.get("text"):
            vars_list.append(f"--text-color: {colors['text']};")
        if colors.get("muted"):
            vars_list.append(f"--muted-color: {colors['muted']};")
        if colors.get("border"):
            vars_list.append(f"--border-color: {colors['border']};")
        if colors.get("btn_bg"):
            vars_list.append(f"--btn-primary-bg: {colors['btn_bg']};")
        if colors.get("btn_text"):
            vars_list.append(f"--btn-primary-text: {colors['btn_text']};")
        if colors.get("error"):
            vars_list.append(f"--color-error: {colors['error']};")
        if colors.get("success"):
            vars_list.append(f"--color-success: {colors['success']};")

        if card.get("width"):
            vars_list.append(f"--card-width: {card['width']};")
        if card.get("radius"):
            vars_list.append(f"--radius-lg: {card['radius']};")

        if inputs.get("height"):
            vars_list.append(f"--input-height: {inputs['height']};")
        if inputs.get("radius"):
            vars_list.append(f"--radius-sm: {inputs['radius']};")
        if inputs.get("bg"):
            vars_list.append(f"--input-bg: {inputs['bg']};")

        if buttons.get("height"):
            vars_list.append(f"--button-height: {buttons['height']};")

        if typography.get("font_family"):
            vars_list.append(f"--font-family: {typography['font_family']};")

        # Branding & Logo Sizing variables
        if branding.get("logo_width"):
            vars_list.append(f"--logo-width: {branding['logo_width']};")
        if branding.get("logo_height"):
            vars_list.append(f"--logo-height: {branding['logo_height']};")
        if branding.get("logo_scale") is not None:
            try:
                scale_factor = float(branding["logo_scale"]) / 100.0
                vars_list.append(f"--logo-scale: {scale_factor:.2f};")
            except (ValueError, TypeError):
                vars_list.append("--logo-scale: 1;")
        if branding.get("logo_align"):
            vars_list.append(f"--logo-align: {branding['logo_align']};")
        maintain_ar = branding.get("maintain_aspect_ratio", True)
        vars_list.append(f"--logo-object-fit: {'contain' if maintain_ar is not False else 'fill'};")

        # OTP Button Customization variables
        if otp_buttons.get("height"):
            vars_list.append(f"--otp-btn-height: {otp_buttons['height']};")
        if otp_buttons.get("icon_size"):
            vars_list.append(f"--otp-btn-icon-size: {otp_buttons['icon_size']};")
        if otp_buttons.get("font_size"):
            vars_list.append(f"--otp-btn-font-size: {otp_buttons['font_size']};")
        if otp_buttons.get("radius"):
            vars_list.append(f"--otp-btn-radius: {otp_buttons['radius']};")
        if otp_buttons.get("gap"):
            vars_list.append(f"--otp-btn-gap: {otp_buttons['gap']};")
        if otp_buttons.get("padding"):
            vars_list.append(f"--otp-btn-padding: {otp_buttons['padding']};")
        if otp_buttons.get("border_width"):
            vars_list.append(f"--otp-btn-border-width: {otp_buttons['border_width']};")
        if otp_buttons.get("width_mode") == "custom" and otp_buttons.get("custom_width"):
            vars_list.append(f"--otp-btn-custom-width: {otp_buttons['custom_width']};")

        return "\n  ".join(vars_list)
