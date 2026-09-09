"""
Template Registry & Dynamic Design Token System (Phases 8 & 9 + Major Enhancement).
Provides a centralized registry of authentication visual templates, default configuration
schemas, and utility to generate dynamic CSS root variables for live customization in the builder.
Supports comprehensive background, card styling, animation, typography, and input/button controls.
"""

import copy
import re


class TemplateRegistry:
    TEMPLATES = {
        "modern": {
            "id": "modern",
            "name": "Modern SaaS",
            "description": "Contemporary SaaS authentication — clean card layout, segmented auth selector, balanced whitespace, and modern dark aesthetic.",
            "badge": "Dark / SaaS",
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
                "background": {
                    "type": "gradient",
                    "color": "#131315",
                    "gradient": {
                        "type": "radial",
                        "start_color": "rgba(198, 198, 198, 0.04)",
                        "end_color": "#131315",
                        "angle": "135deg",
                    },
                    "image_url": "",
                    "position": "center",
                    "size": "cover",
                    "repeat": "no-repeat",
                    "overlay": {
                        "color": "#000000",
                        "opacity": 0,
                    },
                    "blur": 0,
                    "brightness": 100,
                    "saturation": 100,
                },
                "card": {
                    "width": "420px",
                    "max_width": "100%",
                    "padding": "2rem",
                    "background_color": "#201f22",
                    "appearance": "opaque",
                    "opacity": 100,
                    "radius": "12px",
                    "border_enabled": True,
                    "border_width": "1px",
                    "border_opacity": 30,
                    "border_color": "rgba(76, 69, 70, 0.35)",
                    "shadow": "subtle",
                    "shadow_blur": "40px",
                    "shadow_spread": "0px",
                    "blur": "0px",
                    "backdrop_blur": 0,
                    "alignment": "center",
                    "position": "center",
                    "horizontal_position": 50,
                    "vertical_position": 50,
                },
                "theme": {
                    "mode": "dark",
                },
                "animations": {
                    "type": "fade",
                    "duration": "250ms",
                    "delay": "0ms",
                    "intensity": "subtle",
                },
                "colors": {
                    "primary": "#c6c6c6",
                    "primary_hover": "#e2e2e2",
                    "secondary": "#c7c6c6",
                    "background": "#131315",
                    "card_bg": "#201f22",
                    "text": "#e5e1e4",
                    "muted": "#988e90",
                    "border": "rgba(76, 69, 70, 0.35)",
                    "btn_bg": "#c6c6c6",
                    "btn_text": "#1b1b1b",
                    "error": "#ef4444",
                    "success": "#10b981",
                },
                "typography": {
                    "font_family": "Inter, -apple-system, sans-serif",
                    "heading_size": "1.75rem",
                    "body_size": "0.925rem",
                    "label_size": "0.85rem",
                    "button_text_size": "0.875rem",
                    "text_align": "center",
                    "font_weight": "600",
                    "letter_spacing": "-0.025em",
                },
                "inputs": {
                    "height": "42px",
                    "radius": "8px",
                    "bg": "#131315",
                    "border": "rgba(76, 69, 70, 0.35)",
                    "text_color": "#e5e1e4",
                    "focus_ring": "rgba(198, 198, 198, 0.25)",
                },
                "buttons": {
                    "height": "42px",
                    "width": "100%",
                    "radius": "8px",
                    "font_size": "0.875rem",
                    "font_weight": "600",
                    "bg": "#c6c6c6",
                    "text_color": "#1b1b1b",
                    "border": "none",
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
                    "card_position": "center",
                    "card_horizontal_position": 50,
                    "card_vertical_position": 50,
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
                "background": {
                    "type": "color",
                    "color": "#0f172a",
                    "gradient": {
                        "type": "linear",
                        "start_color": "#0f172a",
                        "end_color": "#1e1b4b",
                        "angle": "145deg",
                    },
                    "image_url": "",
                    "position": "center",
                    "size": "cover",
                    "repeat": "no-repeat",
                    "overlay": {
                        "color": "#000000",
                        "opacity": 0,
                    },
                    "blur": 0,
                    "brightness": 100,
                    "saturation": 100,
                },
                "card": {
                    "width": "460px",
                    "max_width": "100%",
                    "padding": "2rem",
                    "background_color": "#ffffff",
                    "appearance": "opaque",
                    "opacity": 100,
                    "radius": "12px",
                    "border_enabled": True,
                    "border_width": "1px",
                    "border_opacity": 30,
                    "border_color": "#e2e8f0",
                    "shadow": "subtle",
                    "shadow_blur": "25px",
                    "shadow_spread": "0px",
                    "blur": "0px",
                    "backdrop_blur": 0,
                    "alignment": "center",
                    "position": "center",
                    "horizontal_position": 50,
                    "vertical_position": 50,
                },
                "theme": {
                    "mode": "dark",
                },
                "animations": {
                    "type": "fade",
                    "duration": "250ms",
                    "delay": "0ms",
                    "intensity": "subtle",
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
                    "button_text_size": "0.875rem",
                    "text_align": "left",
                    "font_weight": "600",
                    "letter_spacing": "-0.025em",
                },
                "inputs": {
                    "height": "42px",
                    "radius": "6px",
                    "bg": "#ffffff",
                    "border": "#cbd5e1",
                    "text_color": "#0f172a",
                    "focus_ring": "rgba(37, 99, 235, 0.15)",
                },
                "buttons": {
                    "height": "44px",
                    "width": "100%",
                    "radius": "6px",
                    "font_size": "0.875rem",
                    "font_weight": "600",
                    "bg": "#2563eb",
                    "text_color": "#ffffff",
                    "border": "none",
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
                    "card_position": "center",
                    "card_horizontal_position": 50,
                    "card_vertical_position": 50,
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
                "background": {
                    "type": "color",
                    "color": "#f8fafc",
                    "gradient": {
                        "type": "linear",
                        "start_color": "#ffffff",
                        "end_color": "#f1f5f9",
                        "angle": "180deg",
                    },
                    "image_url": "",
                    "position": "center",
                    "size": "cover",
                    "repeat": "no-repeat",
                    "overlay": {
                        "color": "#000000",
                        "opacity": 0,
                    },
                    "blur": 0,
                    "brightness": 100,
                    "saturation": 100,
                },
                "card": {
                    "width": "440px",
                    "max_width": "100%",
                    "padding": "2rem",
                    "background_color": "#ffffff",
                    "appearance": "opaque",
                    "opacity": 100,
                    "radius": "10px",
                    "border_enabled": True,
                    "border_width": "1px",
                    "border_opacity": 30,
                    "border_color": "#e2e8f0",
                    "shadow": "subtle",
                    "shadow_blur": "6px",
                    "shadow_spread": "0px",
                    "blur": "0px",
                    "backdrop_blur": 0,
                    "alignment": "center",
                    "position": "center",
                    "horizontal_position": 50,
                    "vertical_position": 50,
                },
                "theme": {
                    "mode": "dark",
                },
                "animations": {
                    "type": "fade",
                    "duration": "200ms",
                    "delay": "0ms",
                    "intensity": "subtle",
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
                    "button_text_size": "0.875rem",
                    "text_align": "left",
                    "font_weight": "600",
                    "letter_spacing": "-0.02em",
                },
                "inputs": {
                    "height": "42px",
                    "radius": "6px",
                    "bg": "#ffffff",
                    "border": "#cbd5e1",
                    "text_color": "#0f172a",
                    "focus_ring": "rgba(15, 23, 42, 0.15)",
                },
                "buttons": {
                    "height": "44px",
                    "width": "100%",
                    "radius": "6px",
                    "font_size": "0.875rem",
                    "font_weight": "600",
                    "bg": "#0f172a",
                    "text_color": "#ffffff",
                    "border": "none",
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
                    "card_position": "center",
                    "card_horizontal_position": 50,
                    "card_vertical_position": 50,
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

    # --------------------------------------------------------------------------
    # 10 CURATED COLOR PALETTES (Dark & Light Accessible Coordinates)
    # --------------------------------------------------------------------------
    COLOR_PALETTES = {
        "midnight": {
            "id": "midnight",
            "name": "Midnight Blue",
            "accent": "#3B82F6",
            "dark": {
                "primary": "#3B82F6",
                "primary_hover": "#2563EB",
                "background": "#0B1120",
                "card_bg": "#111C30",
                "surface": "#111C30",
                "surface_elevated": "#172540",
                "text": "#F8FAFC",
                "muted": "#94A3B8",
                "border": "#1E293B",
                "btn_bg": "#3B82F6",
                "btn_text": "#FFFFFF",
            },
            "light": {
                "primary": "#2563EB",
                "primary_hover": "#1D4ED8",
                "background": "#F8FAFC",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#F1F5F9",
                "text": "#0F172A",
                "muted": "#64748B",
                "border": "#E2E8F0",
                "btn_bg": "#2563EB",
                "btn_text": "#FFFFFF",
            },
        },
        "ocean": {
            "id": "ocean",
            "name": "Ocean",
            "accent": "#06B6D4",
            "dark": {
                "primary": "#06B6D4",
                "primary_hover": "#0891B2",
                "background": "#081A24",
                "card_bg": "#0F2938",
                "surface": "#0F2938",
                "surface_elevated": "#16384C",
                "text": "#F0FDF4",
                "muted": "#94A3B8",
                "border": "#155E75",
                "btn_bg": "#06B6D4",
                "btn_text": "#081A24",
            },
            "light": {
                "primary": "#0284C7",
                "primary_hover": "#0369A1",
                "background": "#F0F9FF",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#E0F2FE",
                "text": "#082F49",
                "muted": "#64748B",
                "border": "#BAE6FD",
                "btn_bg": "#0284C7",
                "btn_text": "#FFFFFF",
            },
        },
        "indigo": {
            "id": "indigo",
            "name": "Indigo",
            "accent": "#6366F1",
            "dark": {
                "primary": "#6366F1",
                "primary_hover": "#4F46E5",
                "background": "#0F172A",
                "card_bg": "#1E1B4B",
                "surface": "#1E1B4B",
                "surface_elevated": "#2E2A72",
                "text": "#F8FAFC",
                "muted": "#A5B4FC",
                "border": "#312E81",
                "btn_bg": "#6366F1",
                "btn_text": "#FFFFFF",
            },
            "light": {
                "primary": "#4F46E5",
                "primary_hover": "#4338CA",
                "background": "#EEF2FF",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#E0E7FF",
                "text": "#1E1B4B",
                "muted": "#6B7280",
                "border": "#C7D2FE",
                "btn_bg": "#4F46E5",
                "btn_text": "#FFFFFF",
            },
        },
        "violet": {
            "id": "violet",
            "name": "Violet",
            "accent": "#8B5CF6",
            "dark": {
                "primary": "#8B5CF6",
                "primary_hover": "#7C3AED",
                "background": "#180D2B",
                "card_bg": "#241442",
                "surface": "#241442",
                "surface_elevated": "#321D5C",
                "text": "#FAF5FF",
                "muted": "#C4B5FD",
                "border": "#4C1D95",
                "btn_bg": "#8B5CF6",
                "btn_text": "#FFFFFF",
            },
            "light": {
                "primary": "#7C3AED",
                "primary_hover": "#6D28D9",
                "background": "#FAF5FF",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#F3E8FF",
                "text": "#2E1065",
                "muted": "#6B7280",
                "border": "#DDD6FE",
                "btn_bg": "#7C3AED",
                "btn_text": "#FFFFFF",
            },
        },
        "emerald": {
            "id": "emerald",
            "name": "Emerald",
            "accent": "#10B981",
            "dark": {
                "primary": "#10B981",
                "primary_hover": "#059669",
                "background": "#061a14",
                "card_bg": "#0b2e24",
                "surface": "#0b2e24",
                "surface_elevated": "#124736",
                "text": "#ECFDF5",
                "muted": "#A7F3D0",
                "border": "#065F46",
                "btn_bg": "#10B981",
                "btn_text": "#062017",
            },
            "light": {
                "primary": "#059669",
                "primary_hover": "#047857",
                "background": "#F0FDF4",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#DCFCE7",
                "text": "#064E3B",
                "muted": "#6B7280",
                "border": "#A7F3D0",
                "btn_bg": "#059669",
                "btn_text": "#FFFFFF",
            },
        },
        "teal": {
            "id": "teal",
            "name": "Teal",
            "accent": "#14B8A6",
            "dark": {
                "primary": "#14B8A6",
                "primary_hover": "#0D9488",
                "background": "#042322",
                "card_bg": "#083B39",
                "surface": "#083B39",
                "surface_elevated": "#0E4F4D",
                "text": "#F0FDFA",
                "muted": "#99F6E4",
                "border": "#115E59",
                "btn_bg": "#14B8A6",
                "btn_text": "#042322",
            },
            "light": {
                "primary": "#0D9488",
                "primary_hover": "#0F766E",
                "background": "#F0FDFA",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#CCFBF1",
                "text": "#134E4A",
                "muted": "#6B7280",
                "border": "#99F6E4",
                "btn_bg": "#0D9488",
                "btn_text": "#FFFFFF",
            },
        },
        "rose": {
            "id": "rose",
            "name": "Rose",
            "accent": "#F43F5E",
            "dark": {
                "primary": "#F43F5E",
                "primary_hover": "#E11D48",
                "background": "#1C0D13",
                "card_bg": "#2E131E",
                "surface": "#2E131E",
                "surface_elevated": "#3F1B2A",
                "text": "#FFF1F2",
                "muted": "#FECDD3",
                "border": "#881337",
                "btn_bg": "#F43F5E",
                "btn_text": "#FFFFFF",
            },
            "light": {
                "primary": "#E11D48",
                "primary_hover": "#BE123C",
                "background": "#FFF1F2",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#FFE4E6",
                "text": "#881337",
                "muted": "#6B7280",
                "border": "#FECDD3",
                "btn_bg": "#E11D48",
                "btn_text": "#FFFFFF",
            },
        },
        "amber": {
            "id": "amber",
            "name": "Amber",
            "accent": "#F59E0B",
            "dark": {
                "primary": "#F59E0B",
                "primary_hover": "#D97706",
                "background": "#1C160C",
                "card_bg": "#2E2211",
                "surface": "#2E2211",
                "surface_elevated": "#423016",
                "text": "#FFFBEB",
                "muted": "#FDE68A",
                "border": "#78350F",
                "btn_bg": "#F59E0B",
                "btn_text": "#1C160C",
            },
            "light": {
                "primary": "#D97706",
                "primary_hover": "#B45309",
                "background": "#FFFBEB",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#FEF3C7",
                "text": "#78350F",
                "muted": "#78716C",
                "border": "#FDE68A",
                "btn_bg": "#D97706",
                "btn_text": "#FFFFFF",
            },
        },
        "slate": {
            "id": "slate",
            "name": "Slate",
            "accent": "#94A3B8",
            "dark": {
                "primary": "#94A3B8",
                "primary_hover": "#CBD5E1",
                "background": "#0F172A",
                "card_bg": "#1E293B",
                "surface": "#1E293B",
                "surface_elevated": "#334155",
                "text": "#F8FAFC",
                "muted": "#94A3B8",
                "border": "#334155",
                "btn_bg": "#94A3B8",
                "btn_text": "#0F172A",
            },
            "light": {
                "primary": "#475569",
                "primary_hover": "#334155",
                "background": "#F8FAFC",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#F1F5F9",
                "text": "#0F172A",
                "muted": "#64748B",
                "border": "#CBD5E1",
                "btn_bg": "#475569",
                "btn_text": "#FFFFFF",
            },
        },
        "graphite": {
            "id": "graphite",
            "name": "Graphite",
            "accent": "#FFFFFF",
            "dark": {
                "primary": "#FFFFFF",
                "primary_hover": "#E2E8F0",
                "background": "#111214",
                "card_bg": "#1B1D21",
                "surface": "#1B1D21",
                "surface_elevated": "#26292E",
                "text": "#F5F5F5",
                "muted": "#A7A7A7",
                "border": "#34373C",
                "btn_bg": "#FFFFFF",
                "btn_text": "#111111",
            },
            "light": {
                "primary": "#17181A",
                "primary_hover": "#2A2C30",
                "background": "#F5F6F8",
                "card_bg": "#FFFFFF",
                "surface": "#FFFFFF",
                "surface_elevated": "#EBECEF",
                "text": "#17181A",
                "muted": "#656970",
                "border": "#D7DADF",
                "btn_bg": "#17181A",
                "btn_text": "#FFFFFF",
            },
        },
    }

    # --------------------------------------------------------------------------
    # 10 COMPLETE DESIGN PRESETS (Coordinated Visual Identities)
    # --------------------------------------------------------------------------
    DESIGN_PRESETS = {
        "midnight-saas": {
            "id": "midnight-saas",
            "name": "Midnight SaaS",
            "description": "Polished dark SaaS with cobalt accents & subtle float",
            "category": "modern",
            "swatches": ["#3B82F6", "#0B1120", "#111C30"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "midnight"},
                "card": {"preset": "elevated", "border_radius": "12px", "border_width": 1},
                "buttons": {"preset": "solid", "radius": "8px"},
                "inputs": {"preset": "bordered", "radius": "8px"},
                "typography": {"preset": "modern", "heading_size": "24px"},
                "spacing": {"density": "comfortable"},
                "animations": {"type": "fade", "preset": "subtle"},
            },
        },
        "ocean-pro": {
            "id": "ocean-pro",
            "name": "Ocean Professional",
            "description": "Fluid marine glassmorphism with cyan accents",
            "category": "creative",
            "swatches": ["#06B6D4", "#081A24", "#0F2938"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "ocean"},
                "card": {"preset": "glass", "border_radius": "14px", "border_width": 1},
                "buttons": {"preset": "gradient", "radius": "8px"},
                "inputs": {"preset": "glass", "radius": "8px"},
                "typography": {"preset": "modern", "heading_size": "24px"},
                "spacing": {"density": "comfortable"},
                "animations": {"type": "slide_up", "preset": "smooth"},
            },
        },
        "indigo-modern": {
            "id": "indigo-modern",
            "name": "Indigo Modern",
            "description": "Contemporary slate and indigo rounded styling",
            "category": "modern",
            "swatches": ["#6366F1", "#0F172A", "#1E1B4B"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "indigo"},
                "card": {"preset": "soft", "border_radius": "16px", "border_width": 1},
                "buttons": {"preset": "pill", "radius": "9999px"},
                "inputs": {"preset": "soft", "radius": "12px"},
                "typography": {"preset": "modern", "heading_size": "24px"},
                "spacing": {"density": "comfortable"},
                "animations": {"type": "fade", "preset": "smooth"},
            },
        },
        "emerald-finance": {
            "id": "emerald-finance",
            "name": "Emerald Finance",
            "description": "Institutional security layout with emerald accents",
            "category": "business",
            "swatches": ["#10B981", "#062017", "#0C3326"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "emerald"},
                "card": {"preset": "bordered", "border_radius": "6px", "border_width": 1},
                "buttons": {"preset": "sharp", "radius": "4px"},
                "inputs": {"preset": "minimal", "radius": "4px"},
                "typography": {"preset": "enterprise", "heading_size": "22px"},
                "spacing": {"density": "compact"},
                "animations": {"type": "fade", "preset": "subtle"},
            },
        },
        "violet-creative": {
            "id": "violet-creative",
            "name": "Violet Creative",
            "description": "Expressive amethyst theme with refined typography",
            "category": "creative",
            "swatches": ["#8B5CF6", "#180D2B", "#241442"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "violet"},
                "card": {"preset": "glass", "border_radius": "16px", "border_width": 1},
                "buttons": {"preset": "pill", "radius": "9999px"},
                "inputs": {"preset": "soft", "radius": "10px"},
                "typography": {"preset": "editorial", "heading_size": "26px"},
                "spacing": {"density": "spacious"},
                "animations": {"type": "scale", "preset": "expressive"},
            },
        },
        "clean-light": {
            "id": "clean-light",
            "name": "Clean Light",
            "description": "Ultra-clean modern SaaS in crisp white & blue",
            "category": "minimal",
            "swatches": ["#2563EB", "#F8FAFC", "#FFFFFF"],
            "config": {
                "theme": {"mode": "light"},
                "palette": {"preset": "midnight"},
                "card": {"preset": "soft", "border_radius": "12px", "border_width": 1},
                "buttons": {"preset": "solid", "radius": "8px"},
                "inputs": {"preset": "bordered", "radius": "8px"},
                "typography": {"preset": "modern", "heading_size": "24px"},
                "spacing": {"density": "comfortable"},
                "animations": {"type": "fade", "preset": "subtle"},
            },
        },
        "executive": {
            "id": "executive",
            "name": "Executive",
            "description": "High-status obsidian & warm amber institutional look",
            "category": "enterprise",
            "swatches": ["#F59E0B", "#1C160C", "#2E2211"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "amber"},
                "card": {"preset": "minimal", "border_radius": "4px", "border_width": 1},
                "buttons": {"preset": "sharp", "radius": "2px"},
                "inputs": {"preset": "minimal", "radius": "2px"},
                "typography": {"preset": "enterprise", "heading_size": "22px"},
                "spacing": {"density": "compact"},
                "animations": {"type": "none", "preset": "none"},
            },
        },
        "minimal-mono": {
            "id": "minimal-mono",
            "name": "Minimalist Mono",
            "description": "Distraction-free monochrome typography & subtle lines",
            "category": "minimal",
            "swatches": ["#FFFFFF", "#111214", "#1B1D21"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "graphite"},
                "card": {"preset": "minimal", "border_radius": "8px", "border_width": 1},
                "buttons": {"preset": "outline", "radius": "6px"},
                "inputs": {"preset": "minimal", "radius": "4px"},
                "typography": {"preset": "minimal", "heading_size": "20px"},
                "spacing": {"density": "compact"},
                "animations": {"type": "none", "preset": "none"},
            },
        },
        "soft-modern": {
            "id": "soft-modern",
            "name": "Soft Modern",
            "description": "Approachable light theme with soft pill surfaces",
            "category": "modern",
            "swatches": ["#E11D48", "#FFF1F2", "#FFFFFF"],
            "config": {
                "theme": {"mode": "light"},
                "palette": {"preset": "rose"},
                "card": {"preset": "soft", "border_radius": "20px", "border_width": 1},
                "buttons": {"preset": "pill", "radius": "9999px"},
                "inputs": {"preset": "soft", "radius": "12px"},
                "typography": {"preset": "modern", "heading_size": "24px"},
                "spacing": {"density": "spacious"},
                "animations": {"type": "fade", "preset": "smooth"},
            },
        },
        "dark-enterprise": {
            "id": "dark-enterprise",
            "name": "Dark Enterprise",
            "description": "Heavy-duty enterprise architecture with slate tokens",
            "category": "enterprise",
            "swatches": ["#94A3B8", "#0F172A", "#1E293B"],
            "config": {
                "theme": {"mode": "dark"},
                "palette": {"preset": "slate"},
                "card": {"preset": "elevated", "border_radius": "8px", "border_width": 1},
                "buttons": {"preset": "solid", "radius": "6px"},
                "inputs": {"preset": "bordered", "radius": "6px"},
                "typography": {"preset": "enterprise", "heading_size": "22px"},
                "spacing": {"density": "comfortable"},
                "animations": {"type": "fade", "preset": "subtle"},
            },
        },
    }

    # --------------------------------------------------------------------------
    # GRADIENT PRESETS
    # --------------------------------------------------------------------------
    GRADIENT_PRESETS = {
        "midnight": {"type": "linear", "start_color": "#0B1120", "end_color": "#1E293B", "angle": 135},
        "ocean": {"type": "linear", "start_color": "#081A24", "end_color": "#0F2938", "angle": 135},
        "aurora": {"type": "linear", "start_color": "#062017", "end_color": "#0F172A", "angle": 135},
        "violet": {"type": "linear", "start_color": "#180D2B", "end_color": "#2E1065", "angle": 135},
        "sunset": {"type": "linear", "start_color": "#1C0D13", "end_color": "#2E131E", "angle": 135},
        "teal": {"type": "linear", "start_color": "#042322", "end_color": "#0E4F4D", "angle": 135},
    }

    @classmethod
    def get_color_palettes(cls):
        """
        Returns COLOR_PALETTES with 'bg' alias added to dark/light token dicts
        for backward compatibility (some code/tests use tokens['bg']).
        """
        result = {}
        for key, pal in cls.COLOR_PALETTES.items():
            enriched = dict(pal)
            for mode in ("dark", "light"):
                if mode in enriched:
                    tokens = dict(enriched[mode])
                    if "background" in tokens and "bg" not in tokens:
                        tokens["bg"] = tokens["background"]
                    enriched[mode] = tokens
            result[key] = enriched
        return result

    @classmethod
    def get_color_palette(cls, palette_id: str):
        return cls.COLOR_PALETTES.get((palette_id or "graphite").strip().lower())

    @classmethod
    def get_design_presets(cls):
        """
        Returns DESIGN_PRESETS normalized for the UI and tests.
        - Keys are underscore-based (midnight_saas instead of midnight-saas)
        - Each preset has flattened keys: theme_mode, palette, card, buttons, inputs, spacing
        - 'minimal' is also aliased as 'minimal_mono'
        """
        result = {}
        for hyphen_key, preset in cls.DESIGN_PRESETS.items():
            under_key = hyphen_key.replace("-", "_")
            cfg = preset.get("config", {})
            normalized = {
                "id": under_key,
                "name": preset.get("name", ""),
                "description": preset.get("description", ""),
                "category": preset.get("category", "modern"),
                "swatches": preset.get("swatches", []),
                # Flatten config keys for templates and tests
                "theme_mode": cfg.get("theme", {}).get("mode", "dark"),
                "palette": cfg.get("palette", {}).get("preset", ""),
                "card": cfg.get("card", {}),
                "buttons": cfg.get("buttons", {}),
                "inputs": cfg.get("inputs", {}),
                "spacing": cfg.get("spacing", {"density": "comfortable"}),
                "typography": cfg.get("typography", {}),
                "animations": cfg.get("animations", {}),
                # Keep the original nested config for the builder JS
                "config": cfg,
            }
            result[under_key] = normalized
        # 'minimal' may still appear as 'minimal_mono' — no extra alias needed if key is already 'minimal_mono'
        return result

    @classmethod
    def get_design_preset(cls, preset_id: str):
        """
        Look up a design preset by ID. Supports both hyphen ('midnight-saas')
        and underscore ('midnight_saas') formats for backward compatibility.
        """
        key = (preset_id or "midnight-saas").strip().lower()
        # Try direct lookup first
        if key in cls.DESIGN_PRESETS:
            return cls.DESIGN_PRESETS[key]
        # Try replacing underscores with hyphens
        hyphenated = key.replace("_", "-")
        return cls.DESIGN_PRESETS.get(hyphenated)

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
    def _deep_merge_dict(cls, base: dict, override: dict) -> dict:
        """Recursively merges dictionary override onto base without losing base defaults."""
        result = copy.deepcopy(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = cls._deep_merge_dict(result[key], val)
            else:
                result[key] = copy.deepcopy(val)
        return result

    @classmethod
    def merge_config(cls, template_id: str, custom_config: dict | None) -> dict:
        config = cls.get_default_config(template_id)
        if "palette" not in config:
            config["palette"] = {"preset": "indigo", "custom_colors": {}}
        if "spacing" not in config:
            config["spacing"] = {"density": "comfortable"}

        if not custom_config or not isinstance(custom_config, dict):
            return config

        for section, values in custom_config.items():
            if section in config and isinstance(values, dict) and isinstance(config[section], dict):
                config[section] = cls._deep_merge_dict(config[section], values)
            else:
                config[section] = values

        if "palette" not in config:
            config["palette"] = {"preset": "indigo", "custom_colors": {}}
        if "spacing" not in config:
            config["spacing"] = {"density": "comfortable"}
        return config

    @classmethod
    def generate_css_variables(cls, *args, **kwargs) -> str:
        """Converts a configuration dict into CSS custom property declarations for :root.
        Supports both generate_css_variables(config) and generate_css_variables(template_id, config).
        """
        if len(args) == 1:
            config = args[0]
        elif len(args) >= 2:
            if isinstance(args[0], str) and isinstance(args[1], dict):
                config = cls.merge_config(args[0], args[1])
            elif isinstance(args[1], dict):
                config = args[1]
            else:
                config = args[0]
        else:
            config = kwargs.get("config") or kwargs.get("custom_config") or {}

        if not isinstance(config, dict):
            config = {}
        colors = config.get("colors", {})
        card = config.get("card", {})
        background = config.get("background", {})
        animations = config.get("animations", {})
        inputs = config.get("inputs", {})
        buttons = config.get("buttons", {})
        typography = config.get("typography", {})
        branding = config.get("branding", {})
        otp_buttons = config.get("otp_buttons", {})
        layout = config.get("layout", {})

        vars_list = []

        # Theme Mode Defaults & Resolution
        theme = config.get("theme", {})
        if not isinstance(theme, dict):
            theme = {}
        theme_mode = (theme.get("mode") or "dark").strip().lower()
        if theme_mode not in ("dark", "light", "system"):
            theme_mode = "dark"

        if theme_mode == "light":
            t_bg = "#F5F6F8"
            t_card_bg = "#FFFFFF"
            t_text = "#17181A"
            t_muted = "#656970"
            t_input_bg = "#FFFFFF"
            t_input_border = "#D7DADF"
            t_input_text = "#17181A"
            t_btn_bg = "#17181A"
            t_btn_text = "#FFFFFF"
            t_border = "#E2E5EA"
            t_focus_ring = "rgba(23, 24, 26, 0.15)"
            t_tab_bg = "#EDEFF2"
            t_tab_border = "#D7DADF"
            t_tab_active_bg = "#FFFFFF"
            t_tab_active_text = "#17181A"
            t_otp_bg = "#FFFFFF"
            t_otp_border = "#D7DADF"
            t_otp_text = "#17181A"
            t_otp_active_bg = "#EDEFF2"
            t_otp_active_border = "#17181A"
        else:
            t_bg = "#111214"
            t_card_bg = "#1B1D21"
            t_text = "#F5F5F5"
            t_muted = "#A7A7A7"
            t_input_bg = "#15171A"
            t_input_border = "#34373C"
            t_input_text = "#F5F5F5"
            t_btn_bg = "#FFFFFF"
            t_btn_text = "#111111"
            t_border = "rgba(255, 255, 255, 0.08)"
            t_focus_ring = "rgba(255, 255, 255, 0.2)"
            t_tab_bg = "#15171A"
            t_tab_border = "#34373C"
            t_tab_active_bg = "#2A2C30"
            t_tab_active_text = "#F5F5F5"
            t_otp_bg = "#15171A"
            t_otp_border = "#34373C"
            t_otp_text = "#F5F5F5"
            t_otp_active_bg = "#2A2C30"
            t_otp_active_border = "#FFFFFF"

        vars_list.append(f"--theme-mode: {theme_mode};")
        vars_list.append(f"--tab-bg: {t_tab_bg};")
        vars_list.append(f"--tab-border: {t_tab_border};")
        vars_list.append(f"--tab-active-bg: {t_tab_active_bg};")
        vars_list.append(f"--tab-active-text: {t_tab_active_text};")
        vars_list.append(f"--otp-channel-bg: {t_otp_bg};")
        vars_list.append(f"--otp-channel-border: {t_otp_border};")
        vars_list.append(f"--otp-channel-text: {t_otp_text};")
        vars_list.append(f"--otp-channel-active-bg: {t_otp_active_bg};")
        vars_list.append(f"--otp-channel-active-border: {t_otp_active_border};")

        # Color Palette Resolution
        palette_conf = config.get("palette", {})
        palette_id = (palette_conf.get("preset") if isinstance(palette_conf, dict) else palette_conf) or ""
        pal_entry = cls.get_color_palette(palette_id)
        if pal_entry:
            pal_data = pal_entry["light"] if theme_mode == "light" else pal_entry["dark"]
            t_bg = pal_data.get("background", t_bg)
            t_card_bg = pal_data.get("card_bg", t_card_bg)
            t_text = pal_data.get("text", t_text)
            t_muted = pal_data.get("muted", t_muted)
            t_border = pal_data.get("border", t_border)
            t_btn_bg = pal_data.get("btn_bg", t_btn_bg)
            t_btn_text = pal_data.get("btn_text", t_btn_text)
            vars_list.append(f"--palette-id: {palette_id};")
            vars_list.append(f"--color-primary: {pal_data['primary'].lower()};")
            vars_list.append(f"--color-primary-hover: {pal_data['primary_hover'].lower()};")
            vars_list.append(f"--color-bg: {pal_data['background'].lower()};")
            vars_list.append(f"--color-surface: {pal_data['surface'].lower()};")
            vars_list.append(f"--color-surface-elevated: {pal_data['surface_elevated'].lower()};")
            if not colors.get("primary"):
                colors["primary"] = pal_data["primary"]
            if not colors.get("primary_hover"):
                colors["primary_hover"] = pal_data["primary_hover"]

        design_preset_id = config.get("design_preset") or ""
        if design_preset_id:
            vars_list.append(f"--design-preset: {design_preset_id};")

        # Spacing / Density Resolution
        spacing_conf = config.get("spacing", {})
        density = (spacing_conf.get("density") if isinstance(spacing_conf, dict) else spacing_conf) or "comfortable"
        vars_list.append(f"--density: {density};")
        if density == "compact":
            vars_list.append("--card-padding: 1.25rem;")
            vars_list.append("--density-card-padding: 20px;")
            vars_list.append("--input-height: 36px;")
            vars_list.append("--button-height: 36px;")
        elif density == "spacious":
            vars_list.append("--card-padding: 2.75rem;")
            vars_list.append("--density-card-padding: 44px;")
            vars_list.append("--input-height: 48px;")
            vars_list.append("--button-height: 48px;")
        else:
            vars_list.append("--density-card-padding: 32px;")

        # Presets Attributes
        card_preset = (card.get("preset") if isinstance(card, dict) else "") or "default"
        btn_preset = (buttons.get("preset") if isinstance(buttons, dict) else "") or "solid"
        input_preset = (inputs.get("preset") if isinstance(inputs, dict) else "") or "bordered"
        vars_list.append(f"--card-preset: {card_preset};")
        vars_list.append(f"--button-preset: {btn_preset};")
        vars_list.append(f"--input-preset: {input_preset};")

        # 1. Colors
        if colors.get("primary"):
            vars_list.append(f"--primary-color: {colors['primary']};")
        if colors.get("primary_hover"):
            vars_list.append(f"--primary-hover: {colors['primary_hover']};")
        if colors.get("secondary"):
            vars_list.append(f"--secondary-color: {colors['secondary']};")

        # Resolve tokens with awareness of theme defaults vs template hardcoded colors
        def resolve_theme_token(custom_val, theme_default, dark_defaults=()):
            if not custom_val:
                return theme_default
            val_clean = str(custom_val).strip().lower()
            if theme_mode == "light" and val_clean in dark_defaults:
                return theme_default
            return custom_val

        bg_col = resolve_theme_token(
            colors.get("background") or background.get("color"),
            t_bg,
            ("#111214", "#131315", "#0f172a", "#f8fafc", "#f1f5f9"),
        )
        vars_list.append(f"--background-color: {bg_col};")

        card_col = resolve_theme_token(
            card.get("background_color") or card.get("card_bg") or colors.get("card_bg"),
            t_card_bg,
            ("#1b1d21", "#201f22", "#131315", "#111214", "#ffffff"),
        )
        vars_list.append(f"--card-background: {card_col};")
        vars_list.append(f"--card-bg-color: {card_col};")

        text_col = resolve_theme_token(
            colors.get("text"),
            t_text,
            ("#f5f5f5", "#e5e1e4", "#ffffff", "#0f172a", "#17181a"),
        )
        vars_list.append(f"--text-color: {text_col};")

        muted_col = resolve_theme_token(
            colors.get("muted"),
            t_muted,
            ("#a7a7a7", "#988e90", "#64748b", "#656970"),
        )
        vars_list.append(f"--muted-color: {muted_col};")

        border_col = resolve_theme_token(
            card.get("border_color") or colors.get("border"),
            t_border,
            ("rgba(255, 255, 255, 0.08)", "rgba(76, 69, 70, 0.35)", "#e2e8f0", "#e2e5ea"),
        )
        vars_list.append(f"--border-color: {border_col};")

        btn_bg_col = resolve_theme_token(
            buttons.get("bg") or colors.get("btn_bg"),
            t_btn_bg,
            ("#ffffff", "#111111", "#17181a", "#c6c6c6"),
        )
        vars_list.append(f"--btn-primary-bg: {btn_bg_col};")

        btn_text_col = resolve_theme_token(
            buttons.get("text_color") or colors.get("btn_text"),
            t_btn_text,
            ("#ffffff", "#111111", "#1b1b1b"),
        )
        vars_list.append(f"--btn-primary-text: {btn_text_col};")

        if colors.get("error"):
            vars_list.append(f"--color-error: {colors['error']};")
        if colors.get("success"):
            vars_list.append(f"--color-success: {colors['success']};")

        # 2. Background Customization
        bg_type = (background.get("type") or "color").strip().lower()
        vars_list.append(f"--auth-bg-type: {bg_type};")

        bg_color = background.get("color") or colors.get("background") or t_bg
        vars_list.append(f"--auth-bg-color: {bg_color};")

        if bg_type == "image" and background.get("image_url"):
            img_url = background["image_url"].replace('"', '\\"')
            vars_list.append(f"--auth-bg-image: url(\"{img_url}\");")
        elif bg_type == "gradient":
            grad = background.get("gradient", {})
            g_type = grad.get("type", "linear")
            c1 = grad.get("start_color", bg_color)
            c2 = grad.get("end_color", "#201f22")
            angle = grad.get("angle", "135deg")
            if g_type == "radial":
                vars_list.append(f"--auth-bg-image: radial-gradient(circle at center, {c1} 0%, {c2} 100%);")
            else:
                vars_list.append(f"--auth-bg-image: linear-gradient({angle}, {c1} 0%, {c2} 100%);")
        else:
            vars_list.append("--auth-bg-image: none;")

        raw_bg_pos = str(background.get("position", "center")).strip().lower()
        bg_pos_map = {
            "center": "center center",
            "top": "center top",
            "bottom": "center bottom",
            "left": "left center",
            "right": "right center",
            "top-left": "left top",
            "top left": "left top",
            "top-right": "right top",
            "top right": "right top",
            "bottom-left": "left bottom",
            "bottom left": "left bottom",
            "bottom-right": "right bottom",
            "bottom right": "right bottom",
        }
        bg_pos = bg_pos_map.get(raw_bg_pos, raw_bg_pos if raw_bg_pos else "center center")
        vars_list.append(f"--auth-bg-position: {bg_pos};")

        bg_size = background.get("size", "cover")
        vars_list.append(f"--auth-bg-size: {bg_size};")

        bg_repeat = background.get("repeat", "no-repeat")
        vars_list.append(f"--auth-bg-repeat: {bg_repeat};")

        # Background Overlay
        overlay = background.get("overlay", {})
        o_color = overlay.get("color", "#000000")
        try:
            o_opacity_val = float(overlay.get("opacity", 0)) / 100.0 if float(overlay.get("opacity", 0)) > 1.0 else float(overlay.get("opacity", 0))
            o_opacity_val = max(0.0, min(1.0, o_opacity_val))
        except (ValueError, TypeError):
            o_opacity_val = 0.0
        vars_list.append(f"--auth-bg-overlay-color: {o_color};")
        vars_list.append(f"--auth-bg-overlay-opacity: {o_opacity_val:.2f};")

        # Background Effects (blur, brightness, saturation)
        try:
            blur_val = max(0, min(20, int(background.get("blur", 0))))
        except (ValueError, TypeError):
            blur_val = 0
        vars_list.append(f"--auth-bg-blur: {blur_val}px;")
        vars_list.append(f"--auth-bg-filter-blur: {blur_val}px;")

        try:
            brightness_val = max(50, min(150, int(background.get("brightness", 100))))
        except (ValueError, TypeError):
            brightness_val = 100
        vars_list.append(f"--auth-bg-brightness: {brightness_val}%;")

        try:
            sat_val = max(0, min(200, int(background.get("saturation", 100))))
        except (ValueError, TypeError):
            sat_val = 100
        vars_list.append(f"--auth-bg-saturation: {sat_val}%;")

        # 3. Card Styling
        c_width = card.get("width")
        if c_width:
            w_str = f"{c_width}px" if str(c_width).isdigit() else str(c_width)
            vars_list.append(f"--card-width: {w_str};")

        c_max_w = card.get("max_width", "100%")
        vars_list.append(f"--card-max-width: {c_max_w};")

        c_padding = card.get("padding")
        if c_padding:
            p_str = f"{c_padding}px" if str(c_padding).isdigit() else str(c_padding)
            vars_list.append(f"--card-padding: {p_str};")

        # Card Appearance & Surface Transparency
        appearance = str(card.get("appearance") or ("glass" if card.get("preset") == "glass" else "opaque")).strip().lower()
        if appearance not in ("opaque", "translucent", "glass"):
            appearance = "opaque"
        vars_list.append(f"--card-appearance: {appearance};")

        # Opacity / Alpha of Card Surface
        card_op_raw = card.get("opacity") if card.get("opacity") is not None else card.get("background_opacity")
        if card_op_raw is None:
            if appearance == "translucent":
                card_alpha = 0.45
            elif appearance == "glass":
                card_alpha = 0.25
            else:
                card_alpha = 1.0
        else:
            try:
                card_alpha = float(card_op_raw) / 100.0 if float(card_op_raw) > 1.0 else float(card_op_raw)
                card_alpha = max(0.0, min(1.0, card_alpha))
            except (ValueError, TypeError):
                card_alpha = 1.0

        def _to_rgba_str(hex_code, alpha):
            h = str(hex_code or "#ffffff").strip().lstrip("#")
            if len(h) == 3:
                h = "".join([c*2 for c in h])
            if len(h) != 6:
                h = "ffffff"
            try:
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
            except ValueError:
                r, g, b = 255, 255, 255
            return f"rgba({r}, {g}, {b}, {alpha:.2f})"

        card_bg_surface = _to_rgba_str(card_col, card_alpha)
        vars_list.append(f"--card-bg-surface: {card_bg_surface};")
        vars_list.append(f"--card-background: {card_bg_surface};")
        vars_list.append(f"--card-opacity: {card_alpha:.2f};")
        vars_list.append(f"--card-surface-alpha: {card_alpha:.2f};")

        # Card Backdrop Blur
        raw_b_blur = card.get("backdrop_blur") if card.get("backdrop_blur") is not None else card.get("blur")
        if raw_b_blur is None:
            card_blur_px = 14 if appearance == "glass" else 0
        else:
            try:
                m_cb = re.search(r"-?\d+", str(raw_b_blur))
                card_blur_px = max(0, min(30, int(m_cb.group(0)))) if m_cb else (14 if appearance == "glass" else 0)
            except Exception:
                card_blur_px = 14 if appearance == "glass" else 0
        vars_list.append(f"--card-backdrop-blur: {card_blur_px}px;")
        vars_list.append(f"--card-blur: {card_blur_px}px;")

        c_radius = card.get("border_radius") or card.get("radius")
        if c_radius:
            r_str = f"{c_radius}px" if str(c_radius).isdigit() else str(c_radius)
            vars_list.append(f"--card-radius: {r_str};")
            vars_list.append(f"--card-border-radius: {r_str};")
            vars_list.append(f"--radius-lg: {r_str};")

        # Border Settings
        border_enabled = card.get("border_enabled", True)
        if isinstance(border_enabled, str):
            border_enabled = border_enabled.lower() not in ("false", "0", "no", "off")
        if not border_enabled:
            vars_list.append("--card-border-width: 0px;")
            vars_list.append("--card-border-color: transparent;")
        else:
            c_bwidth = card.get("border_width", 1)
            try:
                m_bw = re.search(r"-?\d+", str(c_bwidth))
                bw_num = max(1, min(3, int(m_bw.group(0)))) if m_bw else 1
            except Exception:
                bw_num = 1
            vars_list.append(f"--card-border-width: {bw_num}px;")

            raw_b_op = card.get("border_opacity")
            if raw_b_op is None:
                b_alpha = 0.25 if appearance in ("glass", "translucent") else 1.0
            else:
                try:
                    b_alpha = float(raw_b_op) / 100.0 if float(raw_b_op) > 1.0 else float(raw_b_op)
                    b_alpha = max(0.0, min(1.0, b_alpha))
                except (ValueError, TypeError):
                    b_alpha = 0.25
            c_bcolor = card.get("border_color") or colors.get("border") or "#ffffff"
            vars_list.append(f"--card-border-color: {_to_rgba_str(c_bcolor, b_alpha)};")

        # Card Shadow
        shadow_intensity = card.get("shadow", "medium" if appearance == "glass" else "subtle")
        if isinstance(shadow_intensity, str) and ("rgba" in shadow_intensity or "px" in shadow_intensity):
            vars_list.append(f"--card-shadow: {shadow_intensity};")
        else:
            s_blur = card.get("shadow_blur", "30px")
            sb_str = f"{s_blur}px" if str(s_blur).isdigit() else str(s_blur)
            s_spread = card.get("shadow_spread", "0px")
            sp_str = f"{s_spread}px" if str(s_spread).isdigit() else str(s_spread)

            if shadow_intensity == "none":
                vars_list.append("--card-shadow: none;")
            elif shadow_intensity == "strong":
                vars_list.append(f"--card-shadow: 0 20px {sb_str} {sp_str} rgba(0, 0, 0, 0.65);")
            elif shadow_intensity == "medium":
                vars_list.append(f"--card-shadow: 0 12px {sb_str} {sp_str} rgba(0, 0, 0, 0.35);")
            else:  # subtle
                vars_list.append(f"--card-shadow: 0 4px {sb_str} {sp_str} rgba(0, 0, 0, 0.15);")

        c_align = card.get("alignment", "center")
        if c_align == "left":
            vars_list.append("--card-margin-left: 0;")
            vars_list.append("--card-margin-right: auto;")
        elif c_align == "right":
            vars_list.append("--card-margin-left: auto;")
            vars_list.append("--card-margin-right: 0;")
        else:
            vars_list.append("--card-margin-left: auto;")
            vars_list.append("--card-margin-right: auto;")

        # Card Position & Placement (3x3 grid & fine coordinates)
        card_pos = str(layout.get("card_position") or card.get("position") or "center").strip().lower()
        try:
            h_pos = int(layout.get("card_horizontal_position", card.get("horizontal_position", 50)))
            card_x = max(0, min(100, h_pos))
        except (ValueError, TypeError):
            card_x = 50

        try:
            v_pos = int(layout.get("card_vertical_position", card.get("vertical_position", 50)))
            card_y = max(0, min(100, v_pos))
        except (ValueError, TypeError):
            card_y = 50

        vars_list.append(f"--card-position: {card_pos};")
        vars_list.append(f"--card-x: {card_x}%;")
        vars_list.append(f"--card-y: {card_y}%;")
        vars_list.append(f"--card-x-pct: {card_x};")
        vars_list.append(f"--card-y-pct: {card_y};")

        # 4. Entrance Animations
        anim_type = (animations.get("type") or "fade").strip().lower()
        duration = animations.get("duration", "250ms")
        dur_str = f"{duration}ms" if str(duration).isdigit() else str(duration)
        delay = animations.get("delay", "0ms")
        del_str = f"{delay}ms" if str(delay).isdigit() else str(delay)

        anim_name_map = {
            "none": "none",
            "fade": "animFade",
            "slide_up": "animSlideUp",
            "slide-up": "animSlideUp",
            "slide_down": "animSlideDown",
            "slide-down": "animSlideDown",
            "scale": "animScale",
            "float": "animFloat",
            "subtle_float": "animFloat",
            "subtle-float": "animFloat",
        }
        anim_name = anim_name_map.get(anim_type, "animFade")
        if anim_name == "none":
            vars_list.append("--card-animation: none;")
        else:
            vars_list.append(f"--card-animation: {anim_name} {dur_str} cubic-bezier(0.4, 0, 0.2, 1) {del_str} forwards;")
        vars_list.append(f"--card-animation-name: {anim_name};")
        vars_list.append(f"--card-animation-duration: {dur_str};")
        vars_list.append(f"--card-animation-delay: {del_str};")

        # 5. Inputs & Buttons
        if inputs.get("height"):
            vars_list.append(f"--input-height: {inputs['height']};")
        if inputs.get("radius"):
            vars_list.append(f"--radius-sm: {inputs['radius']};")
            vars_list.append(f"--input-radius: {inputs['radius']};")
        inp_bg = resolve_theme_token(inputs.get("bg"), t_input_bg, ("#131315", "#15171a", "#17181a"))
        inp_border = resolve_theme_token(inputs.get("border"), t_input_border, ("#34373c", "rgba(76, 69, 70, 0.35)", "rgba(255, 255, 255, 0.08)"))
        inp_text = resolve_theme_token(inputs.get("text_color"), t_input_text, ("#f5f5f5", "#e5e1e4"))
        vars_list.append(f"--input-bg: {inp_bg};")
        vars_list.append(f"--input-border: {inp_border};")
        vars_list.append(f"--input-text-color: {inp_text};")

        if buttons.get("height"):
            vars_list.append(f"--button-height: {buttons['height']};")
        if buttons.get("radius"):
            vars_list.append(f"--button-radius: {buttons['radius']};")
        if buttons.get("font_size"):
            vars_list.append(f"--button-font-size: {buttons['font_size']};")
        vars_list.append(f"--button-bg: {btn_bg_col};")
        vars_list.append(f"--button-text: {btn_text_col};")

        # 6. Typography
        if typography.get("font_family"):
            vars_list.append(f"--font-family: {typography['font_family']};")
        if typography.get("heading_size"):
            vars_list.append(f"--heading-size: {typography['heading_size']};")
        if typography.get("body_size"):
            vars_list.append(f"--body-size: {typography['body_size']};")
        if typography.get("label_size"):
            vars_list.append(f"--label-size: {typography['label_size']};")
        if typography.get("button_text_size"):
            vars_list.append(f"--btn-font-size: {typography['button_text_size']};")
        if typography.get("text_align"):
            vars_list.append(f"--auth-text-align: {typography['text_align']};")

        # 7. Branding & Logo Sizing variables
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

        # 8. OTP Button Customization variables
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
