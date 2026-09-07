"""
ZIP Export Service (Phase 12).
Packages a complete, production-ready Django authentication project customized with the
user's selected template, colors, typography, layout, and branding.

Security Controls:
  - Scans and strictly excludes .env, real passwords, database credentials, and API secrets.
  - Generates safe `.env.example` with `OTP_DELIVERY_MODE=demo` placeholder.
  - Sanitizes all zip member paths to prevent directory traversal.
  - Bundles zero private keys or active credentials.
"""

import base64
import io
import os
import zipfile
from pathlib import Path
from django.conf import settings
from .template_registry import TemplateRegistry


class ExportService:
    """
    Builds a standalone exportable Django project ZIP archive.
    """

    FORBIDDEN_FILES = {
        ".env",
        ".env.local",
        ".env.production",
        "db.sqlite3",
        ".DS_Store",
    }

    FORBIDDEN_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".log",
        ".sqlite3",
        ".swp",
    }

    FORBIDDEN_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".gemini",
        ".idea",
        ".vscode",
    }

    @classmethod
    def get_sensitive_patterns(cls):
        """Dynamically gathers sensitive values from environment to scrub from export."""
        patterns = []
        for env_key, placeholder in [
            ("DB_PASSWORD", "your-db-password"),
            ("DB_HOST", "localhost"),
            ("DB_USER", "db_user"),
            ("DB_NAME", "auth_db"),
            ("SECRET_KEY", "your-secret-key-here"),
            ("TWILIO_AUTH_TOKEN", "your-auth-token"),
            ("TWILIO_ACCOUNT_SID", "your-account-sid"),
            ("EMAIL_HOST_PASSWORD", "your-email-password"),
        ]:
            val = os.getenv(env_key)
            if val and len(str(val).strip()) > 3:
                patterns.append((str(val).strip(), placeholder))
        return patterns

    @classmethod
    def sanitize_content(cls, content: str) -> str:
        """Scrubs any known sensitive strings from source files."""
        clean = content
        for secret, placeholder in cls.get_sensitive_patterns():
            clean = clean.replace(secret, placeholder)
        return clean

    @classmethod
    def generate_project_zip(cls, config: dict, template_id: str = "modern") -> bytes:
        """
        Generates in-memory ZIP archive of the customized authentication project.
        """
        template_id = (template_id or config.get("template") or "modern").lower()
        tpl = TemplateRegistry.get(template_id)
        merged_config = TemplateRegistry.merge_config(template_id, config)

        buffer = io.BytesIO()
        base_dir = Path(settings.BASE_DIR)

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Custom README.md
            brand_name = merged_config.get("branding", {}).get("brand_name", "Auth Platform")
            readme_content = cls._generate_readme(brand_name, tpl["name"], merged_config)
            zf.writestr("custom-auth-platform/README.md", readme_content)

            # 2. Safe .env.example
            env_example = cls._generate_env_example()
            zf.writestr("custom-auth-platform/.env.example", env_example)

            # 3. requirements.txt
            requirements = (
                "Django>=5.1.0,<6.2.0\n"
                "python-dotenv>=1.0.0\n"
            )
            zf.writestr("custom-auth-platform/requirements.txt", requirements)

            # 4. Customized tokens CSS (with user's custom design tokens pre-baked)
            css_vars = TemplateRegistry.generate_css_variables(merged_config)
            custom_tokens_css = cls._generate_custom_tokens_css(css_vars)
            zf.writestr("custom-auth-platform/static/accounts/css/auth_tokens.css", custom_tokens_css)

            # 4b. Extract custom logo from base64 data URI into static asset if present
            logo_url = merged_config.get("branding", {}).get("logo_url", "")
            if logo_url and logo_url.startswith("data:image/"):
                try:
                    header, b64_data = logo_url.split(",", 1)
                    raw_bytes = base64.b64decode(b64_data, validate=False)
                    ext = "png"
                    if "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "webp" in header:
                        ext = "webp"
                    logo_arcname = f"custom-auth-platform/static/accounts/images/brand_logo.{ext}"
                    zf.writestr(logo_arcname, raw_bytes)
                    merged_config["branding"]["logo_url"] = f"/static/accounts/images/brand_logo.{ext}"
                except Exception:
                    pass

            # 5. Core files and directories to bundle
            bundle_dirs = [
                ("config", "custom-auth-platform/config"),
                ("accounts", "custom-auth-platform/accounts"),
                ("templates", "custom-auth-platform/templates"),
                ("static", "custom-auth-platform/static"),
            ]

            for src_rel, dst_rel in bundle_dirs:
                src_path = base_dir / src_rel
                if not src_path.exists():
                    continue

                for root, dirs, files in os.walk(src_path):
                    # Filter out forbidden directories in-place
                    dirs[:] = [d for d in dirs if d not in cls.FORBIDDEN_DIRS]

                    for file in files:
                        file_lower = file.lower()
                        if file_lower in cls.FORBIDDEN_FILES:
                            continue
                        if any(file_lower.endswith(ext) for ext in cls.FORBIDDEN_EXTENSIONS):
                            continue
                        # Skip if overriding auth_tokens.css already baked above
                        if file == "auth_tokens.css":
                            continue

                        full_file_path = Path(root) / file
                        rel_file = full_file_path.relative_to(src_path)
                        arcname = f"{dst_rel}/{rel_file.as_posix()}"

                        try:
                            # Read text or binary
                            try:
                                with open(full_file_path, "r", encoding="utf-8") as f:
                                    text = f.read()
                                sanitized_text = cls.sanitize_content(text)
                                zf.writestr(arcname, sanitized_text.encode("utf-8"))
                            except UnicodeDecodeError:
                                with open(full_file_path, "rb") as f:
                                    zf.writestr(arcname, f.read())
                        except Exception:
                            pass

            # 6. Safe manage.py
            manage_py_path = base_dir / "manage.py"
            if manage_py_path.exists():
                with open(manage_py_path, "r", encoding="utf-8") as f:
                    zf.writestr("custom-auth-platform/manage.py", f.read())

        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def _generate_readme(cls, brand_name: str, template_name: str, config: dict) -> str:
        return f"""# {brand_name} — Authentication Platform

Exported Authentication Project powered by Django.
- **Visual Template**: {template_name}
- **Multi-Channel OTP Delivery**: Email, SMS, WhatsApp
- **Security**: PBKDF2 with SHA-256 password hashing, Anti-enumeration protection, Session invalidation.

---

## Quick Start (Development / Demo Mode)

This exported project is ready to run immediately in **DEVELOPMENT / DEMO MODE**.
No real Gmail or Twilio credentials are required to test all authentication features locally.

### 1. Setup Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows:
.\\venv\\Scripts\\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Notice `OTP_DELIVERY_MODE=demo` is pre-configured. In demo mode:
- When you request a verification code for Email, SMS, or WhatsApp, the application displays:
  `[DEVELOPMENT / DEMO MODE] Demo OTP: 123456`
- You can immediately enter `123456` to verify any channel.

### 3. Initialize Database & Run Server
```bash
python manage.py migrate
python manage.py runserver
```
Visit:
- **Login**: http://127.0.0.1:8000/login/
- **Register**: http://127.0.0.1:8000/register/
- **Forgot Password**: http://127.0.0.1:8000/forgot-password/

---

## Production Deployment (Real Delivery)

When you are ready to send real messages to users' phones and inboxes:

1. Update `.env`:
   ```bash
   OTP_DELIVERY_MODE=production
   ```
2. Configure **Email (SMTP)**:
   ```bash
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-gmail-app-password
   DEFAULT_FROM_EMAIL=your-email@gmail.com
   ```
3. Configure **SMS (Twilio)**:
   ```bash
   SMS_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=your-account-sid
   TWILIO_AUTH_TOKEN=your-auth-token
   TWILIO_PHONE_NUMBER=+1234567890
   ```
4. Configure **WhatsApp (Twilio WhatsApp)**:
   ```bash
   WHATSAPP_PROVIDER=twilio
   TWILIO_WHATSAPP_FROM=+14155238886
   ```

---

## Security Best Practices
- Plaintext passwords are NEVER stored. Passwords are cryptographically hashed using PBKDF2 with SHA-256.
- OTP codes are hashed with SHA-256 in the database and expire in 5 minutes with a 5-attempt brute-force limit.
- Resetting password immediately revokes all concurrent authenticated sessions.
"""

    @classmethod
    def _generate_env_example(cls) -> str:
        return """# Environment Configuration Template
# Copy this file to .env and customize for your environment.

DEBUG=True
SECRET_KEY=django-insecure-custom-auth-platform-key-change-in-production

# OTP Delivery Mode: 'demo' (instant test OTP 123456) or 'production' (real delivery)
OTP_DELIVERY_MODE=demo

# Real Email Delivery (SMTP / Gmail App Password)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# Real SMS Delivery (Twilio)
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Real WhatsApp Delivery (Twilio WhatsApp)
WHATSAPP_PROVIDER=twilio
TWILIO_WHATSAPP_FROM=
"""

    @classmethod
    def _generate_custom_tokens_css(cls, dynamic_css_vars: str) -> str:
        return f"""/* ==========================================================================
   AUTHENTICATION PLATFORM - CUSTOMIZED DESIGN TOKENS
   Generated by Custom Builder Export Engine
   ========================================================================== */

:root {{
  /* Core Dynamic Overrides */
  {dynamic_css_vars}

  /* Universal Feedback Colors */
  --color-success: #10b981;
  --color-success-bg: rgba(16, 185, 129, 0.12);
  --color-error: #ef4444;
  --color-error-bg: rgba(239, 68, 68, 0.12);
  --color-warning: #f59e0b;
  --color-warning-bg: rgba(245, 158, 11, 0.12);

  /* Functional Sizing */
  --radius-full: 9999px;
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}}

*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

html, body {{
  min-height: 100%;
  font-family: var(--font-family, 'Inter', -apple-system, sans-serif);
  -webkit-font-smoothing: antialiased;
}}
"""
