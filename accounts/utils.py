"""
Accounts Utility Functions & Template Resolver Engine.
Provides clean template selection, persistence in session, and metadata for the
reusable authentication template system (Phases 8 & 9).
"""

import json
from accounts.services.template_registry import TemplateRegistry
from accounts.models import AuthConfigurations

VALID_TEMPLATES = TemplateRegistry.get_all()
DEFAULT_TEMPLATE = "modern"


def resolve_auth_template(request, page_filename):
    """
    Resolves the template file to render based on:
      1. Query param: ?template=modern|split|corporate
      2. Active session preference: request.session['auth_template']
      3. Active session configuration: request.session['active_config_data']['template']
      4. Default fallback: 'modern'
    
    Persists the chosen template into session for seamless cross-page navigation.
    Returns a tuple: (template_path: str, active_template_info: dict)
    """
    param = request.GET.get("template")
    if param:
        param = param.strip().lower()

    session_template = request.session.get("auth_template")
    active_config_data = request.session.get("active_config_data")
    config_template = (active_config_data.get("template") if isinstance(active_config_data, dict) else None)

    if param and param in VALID_TEMPLATES:
        chosen_id = param
        request.session["auth_template"] = chosen_id
    elif session_template and session_template in VALID_TEMPLATES:
        chosen_id = session_template
    elif config_template and config_template in VALID_TEMPLATES:
        chosen_id = config_template
    else:
        chosen_id = DEFAULT_TEMPLATE

    template_info = VALID_TEMPLATES[chosen_id]
    template_path = f"{template_info['dir']}/{page_filename}"
    return template_path, template_info


def get_auth_config_context(request, template_info):
    """
    Resolves custom branding, design tokens, and authentication settings for MAIN pages
    and live preview frames.
    
    Checks:
      1. Direct session active config: request.session.get('active_config_data')
      2. Query param: ?config=<id>
      3. Session active config ID: request.session.get('active_config_id')
      4. Authenticated user's active configuration in AuthConfigurations
      5. Fallback: Template defaults from TemplateRegistry
    """
    template_id = template_info["id"]
    default_config = TemplateRegistry.get_default_config(template_id)

    custom_data = {}
    config_obj = None

    # Priority 1: Direct active config data in session (applied via Builder)
    session_active_data = request.session.get("active_config_data")
    if isinstance(session_active_data, dict) and session_active_data:
        custom_data = session_active_data

    # Priority 2: Query param or session config ID
    if not custom_data:
        target_id = request.GET.get("config") or request.session.get("active_config_id")
        if target_id:
            try:
                config_id_int = int(target_id)
                config_obj = AuthConfigurations.objects.filter(id=config_id_int, is_active=1).first()
            except (ValueError, TypeError):
                config_obj = None

        # Priority 3: Authenticated user's configuration
        if not config_obj and getattr(request, "user", None) and request.user.is_authenticated:
            config_obj = AuthConfigurations.objects.filter(user_id=request.user.id, is_active=1).order_by("-updated_at").first()

        if config_obj and config_obj.configuration_data:
            raw = config_obj.configuration_data
            if isinstance(raw, str):
                try:
                    custom_data = json.loads(raw)
                except Exception:
                    custom_data = {}
            elif isinstance(raw, dict):
                custom_data = raw

    # Strict Cross-Template Isolation:
    # If custom_data was saved or applied for a different template (e.g. Modern Glass dark theme)
    # than the one currently being rendered (e.g. Minimal Corporate light theme),
    # do NOT bleed the other template's visual design tokens (colors, card, typography, etc.)!
    # Only inherit template-agnostic functional settings (authentication toggles, branding).
    filtered_custom = {}
    if custom_data and isinstance(custom_data, dict):
        cfg_template = custom_data.get("template")
        if cfg_template and cfg_template != template_id:
            if "authentication" in custom_data:
                filtered_custom["authentication"] = custom_data["authentication"]
            if "branding" in custom_data:
                filtered_custom["branding"] = custom_data["branding"]
            if "otp_buttons" in custom_data:
                filtered_custom["otp_buttons"] = custom_data["otp_buttons"]
            if "theme" in custom_data:
                filtered_custom["theme"] = custom_data["theme"]
            if "palette" in custom_data:
                filtered_custom["palette"] = custom_data["palette"]
            if "spacing" in custom_data:
                filtered_custom["spacing"] = custom_data["spacing"]
            if "buttons" in custom_data:
                filtered_custom["buttons"] = custom_data["buttons"]
            if "inputs" in custom_data:
                filtered_custom["inputs"] = custom_data["inputs"]
            if "design_preset" in custom_data:
                filtered_custom["design_preset"] = custom_data["design_preset"]
        else:
            filtered_custom = custom_data

    merged = TemplateRegistry.merge_config(template_id, filtered_custom)
    auth_settings = merged.get("authentication", default_config.get("authentication", {}))
    branding = merged.get("branding", default_config.get("branding", {}))
    background = merged.get("background", default_config.get("background", {}))
    card_settings = merged.get("card", default_config.get("card", {}))
    animations = merged.get("animations", default_config.get("animations", {}))
    theme = merged.get("theme", default_config.get("theme", {"mode": "dark"}))
    theme_mode = theme.get("mode", "dark") if isinstance(theme, dict) else "dark"
    palette = merged.get("palette", default_config.get("palette", {"preset": "indigo"}))
    spacing = merged.get("spacing", default_config.get("spacing", {"density": "comfortable"}))
    buttons = merged.get("buttons", default_config.get("buttons", {}))
    inputs = merged.get("inputs", default_config.get("inputs", {}))
    design_preset = merged.get("design_preset", "")
    dynamic_css_vars = TemplateRegistry.generate_css_variables(merged)

    return {
        "auth_settings": auth_settings,
        "branding": branding,
        "background": background,
        "card_settings": card_settings,
        "animations": animations,
        "theme": theme,
        "theme_mode": theme_mode,
        "palette": palette,
        "spacing": spacing,
        "buttons": buttons,
        "inputs": inputs,
        "design_preset": design_preset,
        "dynamic_css_vars": dynamic_css_vars,
        "active_config": merged,
        "active_config_id": config_obj.id if config_obj else request.session.get("active_config_id"),
        "active_config_name": config_obj.configuration_name if config_obj else None,
    }
