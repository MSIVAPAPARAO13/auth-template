# Enterprise Authentication Platform & Template Studio
<img width="1914" height="944" alt="image" src="https://github.com/user-attachments/assets/c1720e9c-68fb-43c8-b8ac-3d35682be1d6" />


A production-ready, highly secure Django authentication platform featuring multi-channel OTP delivery (Email, SMS, WhatsApp), multiple visual design templates, an interactive Custom Builder, database configuration management, and one-click ZIP project export.

---

## Key Features

1. **Multi-Channel OTP Delivery Architecture**:
   - **Email**: SMTP integration (Google Gmail App Password, SendGrid, Amazon SES).
   - **SMS**: Twilio SMS provider integration.
   - **WhatsApp**: Twilio WhatsApp Business API integration.
   - **Demo Mode**: Instant zero-credential local development mode (`OTP_DELIVERY_MODE=demo`) using fixed demo OTP `123456`.
2. **Multiple Visual Template System**:
   - **Modern Glass**: Frosted glassmorphism, dark aesthetic, floating blurred cards, vibrant neon accents.
   - **Split Screen**: Full-height responsive layout with visual brand hero section on the left and form card on the right.
   - **Minimal Corporate**: Clean enterprise layout with subtle borders, refined form hierarchy, and light palette.
3. **Custom Builder (`/builder/`)**:
   - Live interactive 3-panel workspace.
   - Dynamic real-time CSS variable manipulation (no page reloads needed).
   - Device viewport switching: **Desktop** (1200px), **Tablet** (768px), **Mobile** (375px).
   - Multi-screen switcher: Preview **Login**, **Registration**, **Forgot Password**, and **Password Reset** live.
   - Comprehensive controls: Branding, Colors, Typography, Card dimensions, Inputs, Buttons, Auth settings.
4. **Configuration Persistence & Isolation**:
   - Uses the existing `auth_configurations` database table.
   - Strict server-side ownership enforcement (User A cannot view, edit, duplicate, or delete User B's designs).
   - Automatic security scrubbing: Passwords, OTPs, and API credentials are systematically filtered out before persisting.
5. **Sanitized ZIP Project Export**:
   - Generates a standalone, fully-functional Django project matching the user's customized design tokens and selected template.
   - Custom tokens pre-baked into `auth_tokens.css`.
   - Guaranteed secret hygiene: Excludes `.env`, real database passwords, company RDS hosts, and API tokens.
   - Includes `.env.example` pre-configured with `OTP_DELIVERY_MODE=demo`.
6. **Enterprise Security**:
   - Django PBKDF2 SHA-256 password hashing (both `password` and `password_hash` fields synchronized).
   - Zero plaintext passwords in database, logs, templates, or exports.
   - OTP codes stored exclusively as SHA-256 digests with 5-minute expiration and 5-attempt rate limit.
   - Anti-account enumeration on password reset and forgot password endpoints.
   - Automatic concurrent session invalidation upon password reset.

---

## Tech Stack

- **Backend Framework**: Python 3.10+, Django 6.1
- **Database Architecture**: MySQL (Production / AWS RDS unmanaged tables), SQLite (Local dev fallback & in-memory test isolation)
- **Frontend & UI**: HTML5, Vanilla CSS3 (Custom Design Tokens & CSS Variables), Vanilla JavaScript ES6+
- **Security & Cryptography**: PBKDF2 SHA-256 password hashing, SHA-256 OTP hashing, CSRF protection, Clickjacking defense (`SAMEORIGIN`)

---

## Architecture & File Structure

```
auth-template/
├── config/
│   ├── settings.py           # Core Django settings & multi-channel provider config
│   ├── urls.py               # Root URL configuration
│   └── wsgi.py
│
├── accounts/
│   ├── models.py             # Unmanaged database models (AuthUser, AuthOtps, AuthConfigurations)
│   ├── forms.py              # Login, Registration, Reset, and OTP forms
│   ├── backends.py           # Custom dual-field (password & password_hash) auth backend
│   ├── views.py              # Auth views, Builder view, and AJAX API endpoints
│   ├── urls.py               # Application routing table
│   ├── utils.py              # Template resolution & registry helpers
│   ├── services/
│   │   ├── template_registry.py # Visual templates registry & CSS generator
│   │   ├── config_service.py    # AuthConfigurations persistence & authorization
│   │   ├── export_service.py    # Sanitized standalone ZIP project packager
│   │   ├── delivery_service.py  # Multi-channel delivery adapters (Email, SMS, WhatsApp)
│   │   ├── otp_service.py       # OTP generation, SHA-256 hashing, rate limiting
│   │   ├── password_service.py  # PBKDF2 hashing and strength validation
│   │   └── user_service.py      # User creation and identity resolution
│   └── tests.py              # 200+ isolated SQLite test suite
│
├── templates/
│   └── accounts/
│       ├── builder.html               # SaaS Custom Builder 3-panel workspace
│       ├── templates_preview.html     # Visual template gallery showcase
│       ├── dashboard.html             # Authenticated user dashboard
│       ├── components/                # Reusable partials (brand header, OTP input, alerts, etc.)
│       └── templates/
│           ├── modern/                # Modern Glass template views
│           ├── split/                 # Split Screen template views
│           └── corporate/             # Minimal Corporate template views
│
└── static/
    └── accounts/
        ├── css/
        │   ├── auth_tokens.css        # Centralized CSS design tokens & variables
        │   ├── builder.css            # Custom Builder styling & responsive layouts
        │   ├── template_modern.css    # Modern Glass specific styles
        │   ├── template_split.css     # Split Screen specific styles
        │   ├── template_corporate.css # Minimal Corporate specific styles
        │   └── preview.css            # Gallery preview styles
        └── js/
            ├── builder.js             # Live preview controller & API client
            ├── login.js               # Multi-channel login controller
            ├── register.js            # Multi-channel registration controller
            ├── forgot_password.js     # Multi-channel forgot password controller
            └── reset_password.js      # Password reset controller
```

---

## Quick Start & Installation

### 1. Prerequisites
- Python 3.10+
- Virtual environment (`venv`)

### 2. Setup Environment
```bash
# Clone or navigate to the project
cd auth-template

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## Development & Demo OTP Mode

To develop or evaluate the platform **without configuring real Gmail, Twilio SMS, or Twilio WhatsApp accounts**, set:

```env
OTP_DELIVERY_MODE=demo
```

### How Demo Mode Works:
- When a user requests a verification code for Email, SMS, or WhatsApp:
  - No external API requests are made.
  - The application displays a clearly marked banner:
    ```
    [DEVELOPMENT / DEMO MODE] Demo OTP: 123456
    ```
  - The user can instantly type `123456` to complete the verification step.
- In production mode (`OTP_DELIVERY_MODE=production`), demo OTP is strictly disabled, and real messages are dispatched through the configured providers.

---

## Real Provider Configuration (Production Mode)

When ready to dispatch real emails and SMS/WhatsApp messages:

### 1. Email Delivery (SMTP / Gmail App Password)
```env
OTP_DELIVERY_MODE=production
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_16_character_app_password
DEFAULT_FROM_EMAIL=your_email@gmail.com
```

### 2. Mobile SMS Delivery (Twilio)
```env
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. WhatsApp Delivery (Twilio WhatsApp)
```env
WHATSAPP_PROVIDER=twilio
TWILIO_WHATSAPP_FROM=+14155238886
```

---

## Using the Custom Builder (`/builder/`)

1. Start the Django server:
   ```bash
   python manage.py runserver
   ```
2. Navigate to: **`http://127.0.0.1:8000/builder/`**
3. **Customize Design**:
   - **Template**: Choose Modern Glass, Split Screen, or Minimal Corporate.
   - **Colors**: Real-time picker for Primary, Secondary, Background, Card, Text, and Border colors.
   - **Typography**: Select font families and sizing.
   - **Card & Inputs**: Adjust width, border radius, input height, and button dimensions with live sliders.
   - **Auth Settings**: Toggle password login, OTP login, and specific delivery channels (Email, SMS, WhatsApp).
4. **Device Viewport Testing**:
   - Click **Desktop**, **Tablet**, or **Mobile** in the top bar to inspect responsive layout adaptation live.
5. **Multi-Screen Preview**:
   - Click tabs for **Login**, **Register**, **Forgot**, or **Reset** to inspect each form state.
6. **Save & Manage Configurations**:
   - Click **Save** to store the design into your database profile.
   - Click **My Configs** to load, clone, or delete saved designs.
7. **Export Standalone Project**:
   - Click **Export ZIP** to download a production-ready Django project containing your customized design tokens and components.

---

## Database Architecture & RDS Safety

The application operates with existing company RDS database tables using Django unmanaged models:
- `auth_user`
- `auth_otps`
- `auth_configurations`
- `login_configuration`
- `users`

All models specify `managed = False`.
- **Zero RDS Schema Changes**: Never run `makemigrations` or `migrate` against the production database.
- **Testing Isolation**: The automated test suite executes exclusively against in-memory SQLite (`:memory:`), guaranteeing 100% isolation from production RDS.

---

## Running Automated Tests

Run the complete isolated test suite:
```bash
python manage.py test accounts
```

Perform a Django system configuration check:
```bash
python manage.py check
```
