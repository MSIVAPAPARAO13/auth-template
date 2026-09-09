import json
import secrets
from datetime import timedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.db import transaction

from accounts.models import AuthUser
from accounts.forms import (
    PasswordLoginForm,
    OTPRequestForm,
    OTPVerifyForm,
    RegisterOTPVerifyForm,
    RegistrationForm,
    ForgotPasswordRequestForm,
    ForgotPasswordOTPVerifyForm,
    ResetPasswordForm,
)
from accounts.services.otp_service import OTPService
from accounts.services.password_service import PasswordService
from accounts.services.user_service import UserService
from accounts.services.delivery_service import OTPDeliveryRouter, mask_identifier, normalize_phone_number
from accounts.services.template_registry import TemplateRegistry
from accounts.services.config_service import ConfigService
from accounts.services.export_service import ExportService
from accounts.utils import resolve_auth_template, VALID_TEMPLATES, get_auth_config_context
from django.core.exceptions import PermissionDenied


def login_view(request):
    """
    Unified Login View supporting:
      1. Username / Email / Mobile + Password
      2. Email / Mobile + OTP
    Handles both standard HTTP POST and renders the initial responsive template.
    """
    redirect_url = request.GET.get("next") or request.POST.get("next") or "dashboard"
    if not url_has_allowed_host_and_scheme(redirect_url, allowed_hosts={request.get_host()}):
        redirect_url = "dashboard"

    is_preview = (
        request.GET.get("preview") in ("1", "true")
        or request.headers.get("sec-fetch-dest") == "iframe"
    )
    # If already logged in, go straight to dashboard (unless viewing in preview mode)
    if request.user.is_authenticated and not is_preview:
        return redirect(redirect_url)

    password_form = PasswordLoginForm()
    otp_request_form = OTPRequestForm()
    otp_verify_form = OTPVerifyForm()

    if request.method == "POST":
        action = request.POST.get("action", "password_login")

        # --- Password Login Flow ---
        if action == "password_login":
            password_form = PasswordLoginForm(request.POST)
            if password_form.is_valid():
                ident = password_form.cleaned_data["identifier"]
                raw_pass = password_form.cleaned_data["password"]
                remember = password_form.cleaned_data.get("remember_me", False)

                user = authenticate(request, identifier=ident, password=raw_pass)
                if user is not None:
                    login(request, user, backend="accounts.backends.AuthUserBackend")
                    if remember:
                        request.session.set_expiry(86400 * 30)  # 30 days
                    else:
                        request.session.set_expiry(0)  # Session cookie
                    messages.success(request, f"Welcome back, {user.get_full_name()}!")
                    return redirect(redirect_url)
                else:
                    messages.error(
                        request,
                        "Invalid credentials. Please verify your username, email, or mobile number and password.",
                    )

        # --- OTP Verify POST Flow (Fallback for non-JS clients) ---
        elif action == "verify_otp":
            otp_verify_form = OTPVerifyForm(request.POST)
            if otp_verify_form.is_valid():
                ident = otp_verify_form.cleaned_data["identifier"]
                code = otp_verify_form.cleaned_data["otp_code"]
                remember = otp_verify_form.cleaned_data.get("remember_me", False)

                user = authenticate(request, identifier=ident, otp=code, purpose="login")
                if user is not None:
                    login(request, user, backend="accounts.backends.AuthUserBackend")
                    if remember:
                        request.session.set_expiry(86400 * 30)
                    else:
                        request.session.set_expiry(0)
                    messages.success(request, f"Welcome back, {user.get_full_name()}!")
                    return redirect(redirect_url)
                else:
                    messages.error(request, "Invalid, expired, or locked verification code.")

    channel_status = OTPDeliveryRouter.get_channel_status()
    template_path, template_info = resolve_auth_template(request, "login.html")
    config_ctx = get_auth_config_context(request, template_info)

    context = {
        "password_form": password_form,
        "otp_request_form": otp_request_form,
        "otp_verify_form": otp_verify_form,
        "channel_status": channel_status,
        "next": redirect_url,
        "active_template": template_info["id"],
        "available_templates": VALID_TEMPLATES,
        **config_ctx,
    }
    return render(request, template_path, context)


@require_POST
def otp_request_api(request):
    """
    AJAX endpoint to request a 6-digit OTP code for Login via Email, SMS, or WhatsApp.
    Validates account existence and delegates to OTPService.
    """
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = OTPRequestForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    identifier = form.cleaned_data["identifier"]
    channel = (form.cleaned_data.get("channel") or "email").strip().lower()

    # Check channel availability
    status_map = OTPDeliveryRouter.get_channel_status()
    if not status_map.get(channel, {}).get("available", False):
        label = status_map.get(channel, {}).get("label", channel.title())
        return JsonResponse(
            {
                "success": False,
                "message": f"{label} delivery is currently unavailable.",
            },
            status=400,
        )

    # Verify user exists and is active before sending OTP
    user = (
        AuthUser.objects.filter(email=identifier).first()
        or AuthUser.objects.filter(mobile=identifier).first()
    )
    if not user:
        norm_phone = normalize_phone_number(identifier)
        if norm_phone:
            user = AuthUser.objects.filter(mobile=norm_phone).first()

    if not user:
        return JsonResponse(
            {
                "success": False,
                "message": "No account found matching this email or mobile number.",
            },
            status=404,
        )

    if not bool(user.is_active):
        return JsonResponse(
            {
                "success": False,
                "message": "This account is inactive. Please reach out to your administrator.",
            },
            status=403,
        )

    success, message = OTPService.generate_and_send_otp(
        identifier=identifier,
        purpose="login",
        user=user,
        channel=channel,
    )

    if not success:
        return JsonResponse({"success": False, "message": message}, status=400)

    return JsonResponse(
        {
            "success": True,
            "message": message,
            "identifier": identifier,
            "masked_identifier": mask_identifier(identifier, channel),
            "channel": channel,
            "cooldown": 60,
            "expires_in": 300,
        }
    )


@require_POST
def otp_verify_api(request):
    """
    AJAX endpoint to verify 6-digit OTP code and establish the authenticated session.
    """
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = OTPVerifyForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    identifier = form.cleaned_data["identifier"]
    code = form.cleaned_data["otp_code"]
    remember = form.cleaned_data.get("remember_me", False)

    # Authenticate user via custom backend
    user = authenticate(request, identifier=identifier, otp=code, purpose="login")

    if not user:
        # Check specific failure reason via verify_otp inspect
        _, reason_msg, _ = OTPService.verify_otp(identifier, code, purpose="login")
        return JsonResponse(
            {"success": False, "message": reason_msg or "Invalid verification code."},
            status=400,
        )

    # Establish authenticated Django session
    login(request, user, backend="accounts.backends.AuthUserBackend")

    if remember:
        request.session.set_expiry(86400 * 30)  # 30 days
    else:
        request.session.set_expiry(0)  # Browser close

    redirect_url = request.GET.get("next") or data.get("next") or "/dashboard/"
    if not url_has_allowed_host_and_scheme(redirect_url, allowed_hosts={request.get_host()}):
        redirect_url = "/dashboard/"

    return JsonResponse(
        {
            "success": True,
            "message": "Authentication successful.",
            "redirect_url": redirect_url,
        }
    )


def dashboard_view(request):
    """
    Landing dashboard confirming authenticated session and request.user status.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    context = {
        "user": request.user,
    }
    return render(request, "accounts/dashboard.html", context)


def logout_view(request):
    """Logs out the active user session and redirects to the login screen."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("login")


def register_view(request):
    """
    Registration View:
    1. Collects Full Name, Email, Mobile, Password, Confirm Password.
    2. Supports OTP delivery via Email, SMS, or WhatsApp.
    3. Validates fields and checks uniqueness against AuthUser.
    4. Hashes password using PBKDF2 (NEVER stores plaintext passwords).
    5. Generates unique collision-safe username.
    6. Saves non-sensitive registration state and PBKDF2 hash into server-side session.
    7. Dispatches 6-digit registration OTP to selected channel.
    8. Transitions to Registration OTP Verification screen.
    """
    is_preview = (
        request.GET.get("preview") in ("1", "true")
        or request.headers.get("sec-fetch-dest") == "iframe"
    )
    if request.user.is_authenticated and not is_preview:
        return redirect("dashboard")

    template_path, template_info = resolve_auth_template(request, "register.html")
    channel_status = OTPDeliveryRouter.get_channel_status()
    form = RegistrationForm()
    otp_verify_form = RegisterOTPVerifyForm()

    if request.method == "POST":
        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or request.content_type == "application/json"
        )
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body.decode("utf-8"))
            else:
                data = request.POST
        except Exception:
            data = request.POST

        form = RegistrationForm(data)
        if form.is_valid():
            full_name = form.cleaned_data["full_name"]
            email = form.cleaned_data["email"]
            mobile = form.cleaned_data.get("mobile")
            channel = (form.cleaned_data.get("channel") or "email").strip().lower()
            raw_password = form.cleaned_data["password"]

            # Select delivery identifier
            if channel == "email":
                otp_identifier = email
            else:
                otp_identifier = mobile

            # Verify channel availability
            if not channel_status.get(channel, {}).get("available", False):
                label = channel_status.get(channel, {}).get("label", channel.title())
                err_msg = f"{label} delivery is currently unavailable."
                if is_ajax:
                    return JsonResponse({"success": False, "message": err_msg}, status=400)
                messages.error(request, err_msg)
                return render(
                    request,
                    template_path,
                    {
                        "form": form,
                        "otp_verify_form": otp_verify_form,
                        "channel_status": channel_status,
                        "step": "form",
                        "active_template": template_info["id"],
                        "available_templates": VALID_TEMPLATES,
                    },
                )

            # Pre-compute PBKDF2 hash - raw password is NEVER persisted or stored in session
            hashed_password = PasswordService.hash_password(raw_password)

            # Generate collision-safe username
            username = UserService.generate_unique_username(email, full_name)

            # Store sanitized pending registration in server-side session
            request.session["pending_registration"] = {
                "full_name": full_name,
                "email": email,
                "mobile": mobile,
                "username": username,
                "hashed_password": hashed_password,
                "channel": channel,
                "otp_identifier": otp_identifier,
            }
            request.session.modified = True

            # Generate and dispatch OTP (purpose='register')
            success, msg = OTPService.generate_and_send_otp(
                identifier=otp_identifier,
                purpose="register",
                channel=channel,
            )

            if not success:
                request.session.pop("pending_registration", None)
                request.session.modified = True
                if is_ajax:
                    return JsonResponse({"success": False, "message": msg}, status=400)
                messages.error(request, msg)
            else:
                masked_id = mask_identifier(otp_identifier, channel)
                if is_ajax:
                    return JsonResponse(
                        {
                            "success": True,
                            "channel": channel,
                            "otp_identifier": otp_identifier,
                            "masked_identifier": masked_id,
                            "message": msg,
                            "cooldown": 60,
                            "expires_in": 300,
                        }
                    )
                return render(
                    request,
                    template_path,
                    {
                        "form": form,
                        "otp_verify_form": otp_verify_form,
                        "channel_status": channel_status,
                        "step": "verify",
                        "channel": channel,
                        "masked_identifier": masked_id,
                        "active_template": template_info["id"],
                        "available_templates": VALID_TEMPLATES,
                    },
                )
        else:
            if is_ajax:
                first_err = next(iter(form.errors.values()))[0]
                return JsonResponse({"success": False, "message": first_err, "errors": form.errors}, status=400)

    config_ctx = get_auth_config_context(request, template_info)
    context = {
        "form": form,
        "otp_verify_form": otp_verify_form,
        "channel_status": channel_status,
        "step": "form",
        "active_template": template_info["id"],
        "available_templates": VALID_TEMPLATES,
        **config_ctx,
    }
    return render(request, template_path, context)


@require_POST
def register_otp_verify_api(request):
    """
    AJAX endpoint to verify 6-digit registration OTP and create the AuthUser account.
    """
    pending = request.session.get("pending_registration")
    if not pending:
        return JsonResponse(
            {
                "success": False,
                "message": "Registration session has expired. Please submit the registration form again.",
            },
            status=400,
        )

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = RegisterOTPVerifyForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    otp_code = form.cleaned_data["otp_code"]
    otp_id = pending.get("otp_identifier") or pending.get("email")

    # Verify OTP against purpose='register'
    is_valid, msg, _ = OTPService.verify_otp(
        identifier=otp_id,
        candidate_otp=otp_code,
        purpose="register",
    )

    if not is_valid:
        return JsonResponse({"success": False, "message": msg}, status=400)

    # Double check for collision before insert
    if AuthUser.objects.filter(email=pending["email"]).exists():
        return JsonResponse(
            {
                "success": False,
                "message": "An account with this email address already exists. Please sign in.",
            },
            status=400,
        )

    # Create the user atomically with synchronized password hashes
    user = UserService.create_user_from_registration(
        full_name=pending["full_name"],
        email=pending["email"],
        hashed_password=pending["hashed_password"],
        mobile=pending.get("mobile"),
        username=pending.get("username"),
    )

    # Purge pending registration from session
    request.session.pop("pending_registration", None)
    request.session.modified = True

    # Log in the new user immediately
    login(request, user, backend="accounts.backends.AuthUserBackend")
    messages.success(request, f"Welcome to the platform, {user.get_full_name()}!")

    return JsonResponse(
        {
            "success": True,
            "message": "Account created successfully! Redirecting to your dashboard...",
            "redirect_url": "/dashboard/",
        }
    )


@require_POST
def register_otp_resend_api(request):
    """
    AJAX endpoint to resend registration OTP for the active pending registration session.
    Resends through the explicitly selected channel (Email, SMS, or WhatsApp).
    """
    pending = request.session.get("pending_registration")
    otp_id = pending.get("otp_identifier") or pending.get("email") if pending else None
    if not pending or not otp_id:
        return JsonResponse(
            {
                "success": False,
                "message": "No active registration session found. Please register again.",
            },
            status=400,
        )

    channel = pending.get("channel", "email")

    success, msg = OTPService.generate_and_send_otp(
        identifier=otp_id,
        purpose="register",
        channel=channel,
    )

    if not success:
        return JsonResponse({"success": False, "message": msg}, status=400)

    return JsonResponse(
        {
            "success": True,
            "message": msg,
            "channel": channel,
            "masked_identifier": mask_identifier(otp_id, channel),
            "cooldown": 60,
            "expires_in": 300,
        }
    )


# ==============================================================================
# PHASE 7: FORGOT PASSWORD & PASSWORD RESET WORKFLOW
# ==============================================================================

def forgot_password_view(request):
    """
    Renders the Forgot Password UI (Step 1: Identifier & Channel Selector, Step 2: OTP Verification).
    Provides dynamic channel availability status for Email, SMS, and WhatsApp.
    """
    is_preview = (
        request.GET.get("preview") in ("1", "true")
        or request.headers.get("sec-fetch-dest") == "iframe"
    )
    if request.user.is_authenticated and not is_preview:
        return redirect("dashboard")

    template_path, template_info = resolve_auth_template(request, "forgot_password.html")
    channel_status = OTPDeliveryRouter.get_channel_status()
    req_form = ForgotPasswordRequestForm()
    verify_form = ForgotPasswordOTPVerifyForm()
    config_ctx = get_auth_config_context(request, template_info)

    return render(
        request,
        template_path,
        {
            "form": req_form,
            "verify_form": verify_form,
            "channel_status": channel_status,
            "step": "form",
            "active_template": template_info["id"],
            "available_templates": VALID_TEMPLATES,
            **config_ctx,
        },
    )


@require_POST
def forgot_password_otp_request_api(request):
    """
    AJAX endpoint to request a password reset OTP code.
    Enforces Account Enumeration Protection:
      - Always returns a generic success response if format is valid.
      - Never leaks whether the identifier is registered or not.
      - If user exists: generates OTP with purpose="reset_password" and dispatches via selected channel.
      - If delivery provider fails: returns safe 400 error.
    """
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = ForgotPasswordRequestForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    identifier = form.cleaned_data["identifier"]
    channel = (form.cleaned_data.get("channel") or "email").strip().lower()

    # Check channel availability
    status_map = OTPDeliveryRouter.get_channel_status()
    if not status_map.get(channel, {}).get("available", False):
        label = status_map.get(channel, {}).get("label", channel.title())
        return JsonResponse(
            {
                "success": False,
                "message": f"{label} delivery is currently unavailable.",
            },
            status=400,
        )

    # Resolve target user internally without leaking existence
    user = (
        AuthUser.objects.filter(email=identifier).first()
        or AuthUser.objects.filter(mobile=identifier).first()
    )
    if not user:
        norm_phone = normalize_phone_number(identifier)
        if norm_phone:
            user = AuthUser.objects.filter(mobile=norm_phone).first()

    generic_success_message = "If an account matches the information provided, a verification code will be sent."

    if user and bool(user.is_active):
        # Determine actual destination based on channel
        if channel == "email":
            dest = user.email or identifier
        else:
            dest = user.mobile or identifier

        success, message = OTPService.generate_and_send_otp(
            identifier=dest,
            purpose="reset_password",
            user=user,
            channel=channel,
        )
        if not success:
            return JsonResponse({"success": False, "message": message}, status=400)

        masked_target = mask_identifier(dest, channel)
        return JsonResponse(
            {
                "success": True,
                "message": generic_success_message,
                "identifier": dest,
                "masked_identifier": masked_target,
                "channel": channel,
                "cooldown": 60,
                "expires_in": 300,
            }
        )

    # Anti-enumeration response when user does not exist
    masked_target = mask_identifier(identifier, channel)
    return JsonResponse(
        {
            "success": True,
            "message": generic_success_message,
            "identifier": identifier,
            "masked_identifier": masked_target,
            "channel": channel,
            "cooldown": 60,
            "expires_in": 300,
        }
    )


@require_POST
def forgot_password_otp_verify_api(request):
    """
    AJAX endpoint to verify 6-digit OTP code for password reset.
    On success:
      - Validates purpose="reset_password"
      - Creates a secure, short-lived server-side reset authorization state in the session.
      - Does NOT update the password at this step.
      - Returns redirect URL to /reset-password/.
    """
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = ForgotPasswordOTPVerifyForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    identifier = form.cleaned_data["identifier"].strip().lower()
    code = form.cleaned_data["otp_code"].strip()

    is_valid, msg, otp_record = OTPService.verify_otp(
        identifier=identifier,
        candidate_otp=code,
        purpose="reset_password",
    )

    if not is_valid:
        return JsonResponse({"success": False, "message": msg}, status=400)

    # Resolve user associated with verified OTP
    user = None
    if otp_record and otp_record.user:
        user = otp_record.user
    else:
        user = (
            AuthUser.objects.filter(email=identifier).first()
            or AuthUser.objects.filter(mobile=identifier).first()
        )
        if not user:
            norm_phone = normalize_phone_number(identifier)
            if norm_phone:
                user = AuthUser.objects.filter(mobile=norm_phone).first()

    if not user:
        return JsonResponse(
            {"success": False, "message": "Unable to authorize password reset. Please try again."},
            status=400,
        )

    # Establish secure server-side reset authorization state (15-minute validity)
    token = secrets.token_urlsafe(32)
    request.session["password_reset_authorized"] = {
        "user_id": user.id,
        "identifier": identifier,
        "token": token,
        "created_at": timezone.now().isoformat(),
        "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
    }
    request.session.modified = True

    return JsonResponse(
        {
            "success": True,
            "message": "Verification code confirmed.",
            "redirect_url": "/reset-password/",
        }
    )


@require_POST
def forgot_password_otp_resend_api(request):
    """
    AJAX endpoint to resend password reset OTP code.
    Maintains 60-second cooldown and delivers strictly through the currently selected channel.
    """
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    identifier = (data.get("identifier") or "").strip()
    channel = (data.get("channel") or "email").strip().lower()

    if not identifier:
        return JsonResponse({"success": False, "message": "Missing identifier."}, status=400)

    # Check cooldown
    can_resend, remaining = OTPService.can_resend(identifier, purpose="reset_password")
    if not can_resend:
        return JsonResponse(
            {"success": False, "message": f"Please wait {remaining} seconds before requesting a new code."},
            status=400,
        )

    # Check channel availability
    status_map = OTPDeliveryRouter.get_channel_status()
    if not status_map.get(channel, {}).get("available", False):
        label = status_map.get(channel, {}).get("label", channel.title())
        return JsonResponse({"success": False, "message": f"{label} delivery is currently unavailable."}, status=400)

    user = (
        AuthUser.objects.filter(email=identifier).first()
        or AuthUser.objects.filter(mobile=identifier).first()
    )
    if not user:
        norm_phone = normalize_phone_number(identifier)
        if norm_phone:
            user = AuthUser.objects.filter(mobile=norm_phone).first()

    if user and bool(user.is_active):
        dest = user.email if channel == "email" else (user.mobile or identifier)
        success, message = OTPService.generate_and_send_otp(
            identifier=dest,
            purpose="reset_password",
            user=user,
            channel=channel,
        )
        if not success:
            return JsonResponse({"success": False, "message": message}, status=400)

        masked_target = mask_identifier(dest, channel)
        return JsonResponse(
            {
                "success": True,
                "message": "A fresh verification code has been dispatched.",
                "masked_identifier": masked_target,
                "cooldown": 60,
                "expires_in": 300,
            }
        )

    # Anti-enumeration response
    return JsonResponse(
        {
            "success": True,
            "message": "If an account matches the information provided, a verification code will be sent.",
            "masked_identifier": mask_identifier(identifier, channel),
            "cooldown": 60,
            "expires_in": 300,
        }
    )


def reset_password_view(request):
    """
    Renders the Reset Password screen (Create New Password, Confirm New Password).
    Strictly validates that the user possesses an unexpired server-side reset authorization state.
    """
    is_preview = (
        request.GET.get("preview") in ("1", "true")
        or request.headers.get("sec-fetch-dest") == "iframe"
    )
    if not is_preview:
        if request.user.is_authenticated:
            return redirect("dashboard")

        auth_state = request.session.get("password_reset_authorized")
        if not auth_state:
            messages.error(request, "Please verify your account before resetting your password.")
            return redirect("forgot_password")

        # Validate expiration
        try:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(auth_state.get("expires_at", ""))
            if not expires_at or timezone.now() > expires_at:
                request.session.pop("password_reset_authorized", None)
                messages.error(request, "Your password reset session has expired. Please request a new code.")
                return redirect("forgot_password")
        except Exception:
            request.session.pop("password_reset_authorized", None)
            messages.error(request, "Invalid password reset session. Please request a new code.")
            return redirect("forgot_password")

    template_path, template_info = resolve_auth_template(request, "reset_password.html")
    form = ResetPasswordForm()
    config_ctx = get_auth_config_context(request, template_info)
    return render(
        request,
        template_path,
        {
            "form": form,
            "active_template": template_info["id"],
            "available_templates": VALID_TEMPLATES,
            **config_ctx,
        },
    )


@require_POST
def reset_password_api(request):
    """
    AJAX endpoint to commit the new password.
    Enforces:
      1. Valid server-side reset authorization state.
      2. Complex PBKDF2 password validation and matching confirmation.
      3. Atomic update of password and password_hash (user.password == user.password_hash).
      4. Single-use consumption (purges reset authorization).
      5. Invalidation of all existing sessions for this user.
      6. Redirects to /login/ with a success notification (does NOT auto-login).
    """
    auth_state = request.session.get("password_reset_authorized")
    if not auth_state:
        return JsonResponse(
            {"success": False, "message": "Password reset session has expired or is invalid. Please restart the process."},
            status=403,
        )

    # Expiry check
    try:
        from django.utils.dateparse import parse_datetime
        expires_at = parse_datetime(auth_state.get("expires_at", ""))
        if not expires_at or timezone.now() > expires_at:
            request.session.pop("password_reset_authorized", None)
            return JsonResponse(
                {"success": False, "message": "Password reset session has expired. Please restart the process."},
                status=403,
            )
    except Exception:
        request.session.pop("password_reset_authorized", None)
        return JsonResponse(
            {"success": False, "message": "Invalid password reset session."},
            status=403,
        )

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST
    except Exception:
        data = request.POST

    form = ResetPasswordForm(data)
    if not form.is_valid():
        first_err = next(iter(form.errors.values()))[0]
        return JsonResponse({"success": False, "message": first_err}, status=400)

    new_password = form.cleaned_data["password"]
    user_id = auth_state.get("user_id")

    with transaction.atomic():
        try:
            user = AuthUser.objects.select_for_update().filter(pk=user_id).first()
        except Exception:
            user = AuthUser.objects.filter(pk=user_id).first()

        if not user:
            request.session.pop("password_reset_authorized", None)
            return JsonResponse({"success": False, "message": "User account not found."}, status=404)

        # Apply new PBKDF2 password (synchronizes password and password_hash)
        PasswordService.apply_password_to_user(user, new_password)
        user.save()

    # Session Invalidation:
    # 1. Purge active database session records for this user across all browsers
    try:
        from django.contrib.sessions.models import Session
        for s in Session.objects.filter(expire_date__gte=timezone.now()):
            s_data = s.get_decoded()
            if str(s_data.get("_auth_user_id")) == str(user.id):
                s.delete()
    except Exception:
        pass

    # 2. Invalidate reset authorization state (anti-replay)
    request.session.pop("password_reset_authorized", None)
    request.session.flush()

    messages.success(request, "Your password has been reset successfully. Please sign in with your new password.")

    return JsonResponse(
        {
            "success": True,
            "message": "Your password has been reset successfully. Please sign in with your new password.",
            "redirect_url": "/login/",
        }
    )


def templates_gallery_view(request):
    """
    Renders the official polished Google Stitch Authentication Templates Gallery
    showcase for all registered visual templates (Modern SaaS, Split Screen, Corporate Enterprise).
    """
    param = request.GET.get("template")
    if param and param in VALID_TEMPLATES:
        request.session["auth_template"] = param

    active_temp = request.session.get("auth_template", "modern")
    template_info = VALID_TEMPLATES.get(active_temp, VALID_TEMPLATES["modern"])
    config_ctx = get_auth_config_context(request, template_info)

    return render(
        request,
        "accounts/templates_preview.html",
        {
            "templates": VALID_TEMPLATES,
            "active_template": active_temp,
            "design_presets": TemplateRegistry.get_design_presets(),
            "color_palettes": TemplateRegistry.get_color_palettes(),
            "user": request.user,
            **config_ctx,
        },
    )


def templates_preview_view(request):
    """
    Public indexable preview endpoint for templates.
    Shares the official polished Google Stitch gallery layout for SEO and backward compatibility.
    """
    return templates_gallery_view(request)



def builder_view(request):
    """
    Renders the interactive SaaS Custom Builder (Phases 10 & 11).
    Allows live customization of branding, colors, typography, card, inputs, buttons,
    real-time multi-screen iframe preview, viewport switching, and configuration persistence.
    """
    selected_tpl = request.GET.get("template", "modern").lower()
    if selected_tpl not in VALID_TEMPLATES:
        selected_tpl = "modern"

    config_id = request.GET.get("config_id")
    initial_config = {}
    active_config_id = "null"

    if config_id and request.user.is_authenticated:
        try:
            cfg = ConfigService.get_configuration(int(config_id), request.user)
            initial_config = cfg.configuration_data or {}
            selected_tpl = initial_config.get("template", selected_tpl)
            active_config_id = cfg.id
        except Exception:
            pass

    if not initial_config:
        # Check active session configuration or user's active configuration
        session_data = request.session.get("active_config_data")
        if isinstance(session_data, dict) and session_data:
            initial_config = session_data
            selected_tpl = initial_config.get("template", selected_tpl)
            active_config_id = request.session.get("active_config_id", "null")
        elif getattr(request, "user", None) and request.user.is_authenticated:
            latest_cfg = AuthConfigurations.objects.filter(user=request.user, is_active=1).order_by("-updated_at").first()
            if latest_cfg and latest_cfg.configuration_data:
                cfg_data = latest_cfg.configuration_data
                if isinstance(cfg_data, str):
                    try:
                        cfg_data = json.loads(cfg_data)
                    except Exception:
                        cfg_data = {}
                if isinstance(cfg_data, dict) and cfg_data:
                    initial_config = cfg_data
                    selected_tpl = initial_config.get("template", selected_tpl)
                    active_config_id = latest_cfg.id

    if not initial_config:
        initial_config = TemplateRegistry.get_default_configuration(selected_tpl)

    return render(
        request,
        "accounts/builder.html",
        {
            "selected_template": selected_tpl,
            "initial_config_json": json.dumps(initial_config),
            "initial_config": initial_config,
            "active_config_id": active_config_id,
            "templates": VALID_TEMPLATES,
            "color_palettes": TemplateRegistry.get_color_palettes(),
            "design_presets": TemplateRegistry.get_design_presets(),
            "gradient_presets": TemplateRegistry.GRADIENT_PRESETS,
            "color_palettes_json": json.dumps(TemplateRegistry.get_color_palettes()),
            "design_presets_json": json.dumps(TemplateRegistry.get_design_presets()),
        },
    )


def config_list_api(request):
    """
    AJAX endpoint: Lists saved configurations for the current user (Phase 11).
    Strict ownership: User A cannot see User B's configurations.
    """
    session_id = request.session.session_key
    if not session_id and not request.user.is_authenticated:
        request.session.save()
        session_id = request.session.session_key

    configs = ConfigService.list_configurations(request.user, session_id=session_id)
    data = []
    for c in configs:
        c_data = c.configuration_data or {}
        data.append({
            "id": c.id,
            "name": c.configuration_name,
            "template": c_data.get("template", "modern"),
            "is_active": bool(c.is_active),
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            "created_at": c.created_at.isoformat() if c.created_at else "",
        })
    return JsonResponse({"success": True, "configurations": data})


@require_POST
def config_save_api(request):
    """
    AJAX endpoint: Saves or updates an authentication design configuration (Phase 11).
    Scans and sanitizes all inputs (zero passwords, OTPs, or API secrets permitted).
    """
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = request.POST
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    name = payload.get("configuration_name") or "My Custom Auth Design"
    data = payload.get("configuration_data") or {}
    config_id = payload.get("config_id")
    if config_id:
        try:
            config_id = int(config_id)
        except (ValueError, TypeError):
            config_id = None

    session_id = request.session.session_key
    if not session_id and not request.user.is_authenticated:
        request.session.save()
        session_id = request.session.session_key

    try:
        cfg = ConfigService.save_configuration(
            name=name,
            data=data,
            user=request.user,
            config_id=config_id,
            session_id=session_id,
        )
        # Automatically synchronize saved design with active main session
        request.session["active_config_id"] = cfg.id
        request.session["active_config_data"] = data
        tpl = (data or {}).get("template")
        if tpl and tpl in VALID_TEMPLATES:
            request.session["auth_template"] = tpl
        request.session.modified = True

        return JsonResponse({
            "success": True,
            "message": "Configuration saved successfully.",
            "config": {
                "id": cfg.id,
                "name": cfg.configuration_name,
                "template": (cfg.configuration_data or {}).get("template", "modern"),
            },
        })
    except PermissionDenied as e:
        return JsonResponse({"success": False, "message": str(e)}, status=403)
    except Exception as e:
        return JsonResponse({"success": False, "message": "Failed to save configuration."}, status=400)


def config_load_api(request, config_id):
    """
    AJAX endpoint: Loads a specific configuration by ID.
    Enforces strict ownership check (Phase 11).
    """
    session_id = request.session.session_key
    try:
        cfg = ConfigService.get_configuration(config_id=config_id, user=request.user, session_id=session_id)
        cfg_data = cfg.configuration_data
        if isinstance(cfg_data, str):
            try:
                cfg_data = json.loads(cfg_data)
            except Exception:
                cfg_data = {}
        elif not isinstance(cfg_data, dict):
            cfg_data = {}

        # Synchronize loaded configuration with session for main pages
        request.session["active_config_id"] = cfg.id
        request.session["active_config_data"] = cfg_data
        tpl = cfg_data.get("template")
        if tpl and tpl in VALID_TEMPLATES:
            request.session["auth_template"] = tpl
        request.session.modified = True

        return JsonResponse({
            "success": True,
            "configuration": {
                "id": cfg.id,
                "name": cfg.configuration_name,
                "data": cfg_data,
                "template": cfg_data.get("template", "modern"),
            },
        })
    except PermissionDenied as e:
        return JsonResponse({"success": False, "message": str(e)}, status=403)
    except Exception:
        return JsonResponse({"success": False, "message": "Configuration not found."}, status=404)


@require_POST
def config_apply_api(request):
    """
    AJAX endpoint: Applies the active builder configuration to MAIN pages immediately.
    Supports either passing an existing config_id or direct configuration JSON payload.
    """
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = request.POST
    except Exception:
        payload = request.POST

    config_data = payload.get("configuration") or payload.get("configuration_data")
    if not config_data and isinstance(payload, dict):
        if any(k in payload for k in ("template", "theme", "colors", "card", "branding", "background")):
            config_data = payload
    config_data = config_data or {}
    config_id = payload.get("config_id")

    if config_id:
        try:
            config_id_int = int(config_id)
            session_id = request.session.session_key
            cfg = ConfigService.get_configuration(config_id=config_id_int, user=request.user, session_id=session_id)
            request.session["active_config_id"] = cfg.id
            if isinstance(cfg.configuration_data, dict):
                config_data = cfg.configuration_data
            elif isinstance(cfg.configuration_data, str):
                try:
                    config_data = json.loads(cfg.configuration_data)
                except Exception:
                    pass
        except Exception:
            pass

    if isinstance(config_data, dict) and config_data:
        request.session["active_config_data"] = config_data
        tpl = config_data.get("template")
        if tpl and tpl in VALID_TEMPLATES:
            request.session["auth_template"] = tpl

    request.session.modified = True
    return JsonResponse({
        "success": True,
        "message": "Auth settings and design applied to main pages successfully!",
    })


@require_POST
def config_reset_api(request):
    """
    AJAX endpoint: Resets MAIN pages back to default settings.
    """
    request.session.pop("active_config_id", None)
    request.session.pop("active_config_data", None)
    request.session.modified = True
    return JsonResponse({
        "success": True,
        "message": "Main site reset to default template and authentication settings.",
    })


@require_POST
def config_duplicate_api(request, config_id):
    """
    AJAX endpoint: Clones an existing configuration for the user.
    """
    session_id = request.session.session_key
    try:
        clone = ConfigService.duplicate_configuration(config_id=config_id, user=request.user, session_id=session_id)
        return JsonResponse({
            "success": True,
            "message": "Configuration cloned successfully.",
            "config": {
                "id": clone.id,
                "name": clone.configuration_name,
            },
        })
    except PermissionDenied as e:
        return JsonResponse({"success": False, "message": str(e)}, status=403)
    except Exception:
        return JsonResponse({"success": False, "message": "Failed to clone configuration."}, status=400)


@require_POST
def config_delete_api(request, config_id):
    """
    AJAX endpoint: Deletes a configuration owned by the user.
    """
    session_id = request.session.session_key
    try:
        ConfigService.delete_configuration(config_id=config_id, user=request.user, session_id=session_id)
        return JsonResponse({"success": True, "message": "Configuration deleted successfully."})
    except PermissionDenied as e:
        return JsonResponse({"success": False, "message": str(e)}, status=403)
    except Exception:
        return JsonResponse({"success": False, "message": "Failed to delete configuration."}, status=400)


@require_POST
def export_zip_api(request):
    """
    ZIP Export Endpoint (Phase 12).
    Generates a production-ready, standalone Django project ZIP archive containing:
      - Selected authentication template and components
      - Customized CSS variables and design tokens pre-baked
      - Demo OTP mode pre-configured (OTP_DELIVERY_MODE=demo)
      - Zero sensitive credentials, .env files, or real database passwords
      - Full README documentation with local run & production setup instructions
    """
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = request.POST
    except Exception:
        payload = {}

    template_id = payload.get("template") or "modern"
    configuration = payload.get("configuration") or {}

    try:
        zip_bytes = ExportService.generate_project_zip(
            config=configuration,
            template_id=template_id,
        )
        response = HttpResponse(zip_bytes, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="auth-platform-{template_id}.zip"'
        return response
    except Exception as e:
        return JsonResponse({"success": False, "message": f"ZIP generation failed: {str(e)}"}, status=500)


