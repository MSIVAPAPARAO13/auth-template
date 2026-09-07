import re
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from accounts.models import AuthUser
from accounts.services.password_service import PasswordService
from accounts.services.delivery_service import normalize_phone_number, is_valid_e164


class PasswordLoginForm(forms.Form):
    """Form for standard credentials login (Username, Email, or Mobile + Password)."""

    identifier = forms.CharField(
        max_length=254,
        label="Username, Email, or Mobile",
        widget=forms.TextInput(
            attrs={
                "id": "password-identifier",
                "class": "form-input",
                "placeholder": "Username, email, or mobile",
                "autocomplete": "username",
                "required": "required",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "id": "password-input",
                "class": "form-input password-field",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
                "required": "required",
            }
        ),
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label="Remember me",
        widget=forms.CheckboxInput(attrs={"id": "remember-me", "class": "form-checkbox"}),
    )

    def clean_identifier(self):
        ident = self.cleaned_data.get("identifier", "").strip()
        if not ident:
            raise ValidationError("Please provide your username, email, or mobile number.")
        return ident

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not password:
            raise ValidationError("Please enter your password.")
        return password


class OTPRequestForm(forms.Form):
    """Form to request a 6-digit OTP verification code via Email, SMS, or WhatsApp."""

    channel = forms.ChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")],
        initial="email",
        required=False,
        widget=forms.HiddenInput(attrs={"id": "otp-channel"}),
    )
    identifier = forms.CharField(
        max_length=254,
        label="Email or Mobile",
        widget=forms.TextInput(
            attrs={
                "id": "otp-identifier",
                "class": "form-input",
                "placeholder": "name@company.com or mobile with country code",
                "autocomplete": "email tel",
                "required": "required",
            }
        ),
    )

    def clean_channel(self):
        channel = (self.cleaned_data.get("channel") or "email").strip().lower()
        if channel not in ("email", "sms", "whatsapp"):
            return "email"
        return channel

    def clean_identifier(self):
        ident = self.cleaned_data.get("identifier", "").strip()
        channel = self.cleaned_data.get("channel") or self.data.get("channel", "email")
        channel = (channel or "email").strip().lower()

        if not ident:
            raise ValidationError("Please provide your email address or mobile number.")

        if channel == "email" or "@" in ident:
            try:
                validate_email(ident)
            except ValidationError:
                raise ValidationError("Please enter a valid email address.")
            return ident.lower()
        else:
            # E.164 phone validation for SMS and WhatsApp
            norm_phone = normalize_phone_number(ident)
            if not is_valid_e164(norm_phone):
                raise ValidationError("Please enter a valid mobile number with country code (e.g. +919876543210).")
            return norm_phone


class OTPVerifyForm(forms.Form):
    """Form to submit and verify the 6-digit OTP."""

    identifier = forms.CharField(
        max_length=254,
        widget=forms.HiddenInput(attrs={"id": "verify-identifier"}),
    )
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Verification Code",
        widget=forms.TextInput(
            attrs={
                "id": "otp-code-input",
                "class": "form-input otp-code-field",
                "placeholder": "••••••",
                "maxlength": "6",
                "pattern": "[0-9]{6}",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "required": "required",
            }
        ),
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label="Remember me",
        widget=forms.CheckboxInput(attrs={"id": "otp-remember-me", "class": "form-checkbox"}),
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get("otp_code", "").strip()
        if not code or len(code) != 6 or not code.isdigit():
            raise ValidationError("Please enter a valid 6-digit numeric verification code.")
        return code


class RegisterOTPVerifyForm(forms.Form):
    """Form to submit and verify the 6-digit OTP during registration."""

    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Verification Code",
        widget=forms.TextInput(
            attrs={
                "id": "reg-otp-code-input",
                "class": "form-input otp-code-field",
                "placeholder": "••••••",
                "maxlength": "6",
                "pattern": "[0-9]{6}",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "required": "required",
            }
        ),
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get("otp_code", "").strip()
        if not code or len(code) != 6 or not code.isdigit():
            raise ValidationError("Please enter a valid 6-digit numeric verification code.")
        return code


class RegistrationForm(forms.Form):
    """Form to collect and validate user registration details."""

    full_name = forms.CharField(
        max_length=150,
        min_length=2,
        label="Full Name",
        widget=forms.TextInput(
            attrs={
                "id": "reg-full-name",
                "class": "form-input",
                "placeholder": "e.g. Jane Doe",
                "autocomplete": "name",
                "required": "required",
            }
        ),
    )
    email = forms.EmailField(
        max_length=254,
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "id": "reg-email",
                "class": "form-input",
                "placeholder": "jane@company.com",
                "autocomplete": "email",
                "required": "required",
            }
        ),
    )
    mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Mobile Number",
        widget=forms.TextInput(
            attrs={
                "id": "reg-mobile",
                "class": "form-input",
                "placeholder": "e.g. +91 9876543210 (required for SMS/WhatsApp)",
                "autocomplete": "tel",
            }
        ),
    )
    channel = forms.ChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")],
        initial="email",
        required=False,
        widget=forms.HiddenInput(attrs={"id": "reg-channel"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "id": "reg-password",
                "class": "form-input password-field",
                "placeholder": "Create a strong password",
                "autocomplete": "new-password",
                "required": "required",
            }
        ),
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "id": "reg-confirm-password",
                "class": "form-input password-field",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
                "required": "required",
            }
        ),
    )

    def clean_channel(self):
        channel = (self.cleaned_data.get("channel") or "email").strip().lower()
        if channel not in ("email", "sms", "whatsapp"):
            return "email"
        return channel

    def clean_full_name(self):
        name = self.cleaned_data.get("full_name", "").strip()
        if len(name) < 2:
            raise ValidationError("Please provide your full name (at least 2 characters).")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if AuthUser.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists. Please sign in instead.")
        return email

    def clean_mobile(self):
        mobile = self.cleaned_data.get("mobile", "").strip()
        if not mobile:
            return None
        norm_phone = normalize_phone_number(mobile)
        if not is_valid_e164(norm_phone):
            raise ValidationError("Please enter a valid mobile number with country code (e.g. +919876543210).")
        if (
            AuthUser.objects.filter(mobile=norm_phone).exists()
            or AuthUser.objects.filter(mobile=mobile).exists()
        ):
            raise ValidationError("An account with this mobile number already exists.")
        return norm_phone

    def clean(self):
        cleaned_data = super().clean()
        channel = cleaned_data.get("channel", "email")
        mobile = cleaned_data.get("mobile")

        if channel in ("sms", "whatsapp") and not mobile:
            self.add_error("mobile", f"Mobile number is required for {channel.upper()} verification.")

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password:
            if password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match. Please verify and re-enter.")
            else:
                errors = PasswordService.validate_password_strength(password)
                if errors:
                    for err in errors:
                        self.add_error("password", err)

        return cleaned_data


class ForgotPasswordRequestForm(forms.Form):
    """Form to submit an email or mobile identifier and choose an OTP channel for password reset."""

    channel = forms.ChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")],
        initial="email",
        required=False,
        widget=forms.HiddenInput(attrs={"id": "forgot-channel"}),
    )
    identifier = forms.CharField(
        max_length=254,
        label="Email or Mobile Number",
        widget=forms.TextInput(
            attrs={
                "id": "forgot-identifier",
                "class": "form-input",
                "placeholder": "name@company.com or mobile with country code",
                "autocomplete": "email tel",
                "required": "required",
            }
        ),
    )

    def clean_channel(self):
        channel = (self.cleaned_data.get("channel") or "email").strip().lower()
        if channel not in ("email", "sms", "whatsapp"):
            return "email"
        return channel

    def clean_identifier(self):
        ident = self.cleaned_data.get("identifier", "").strip()
        channel = self.cleaned_data.get("channel") or self.data.get("channel", "email")
        channel = (channel or "email").strip().lower()

        if not ident:
            raise ValidationError("Please provide your email address or mobile number.")

        if channel == "email" or "@" in ident:
            try:
                validate_email(ident)
            except ValidationError:
                raise ValidationError("Please enter a valid email address.")
            return ident.lower()
        else:
            # E.164 phone validation for SMS and WhatsApp
            norm_phone = normalize_phone_number(ident)
            if not is_valid_e164(norm_phone):
                raise ValidationError("Please enter a valid mobile number with country code (e.g. +919876543210).")
            return norm_phone


class ForgotPasswordOTPVerifyForm(forms.Form):
    """Form to submit and verify the 6-digit OTP code for password reset."""

    identifier = forms.CharField(
        max_length=254,
        widget=forms.HiddenInput(attrs={"id": "forgot-verify-identifier"}),
    )
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Verification Code",
        widget=forms.TextInput(
            attrs={
                "id": "forgot-otp-code-input",
                "class": "form-input otp-code-field",
                "placeholder": "••••••",
                "maxlength": "6",
                "pattern": "[0-9]{6}",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "required": "required",
            }
        ),
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get("otp_code", "").strip()
        if not code or len(code) != 6 or not code.isdigit():
            raise ValidationError("Please enter a valid 6-digit numeric verification code.")
        return code


class ResetPasswordForm(forms.Form):
    """Form to validate and set the new password following verified OTP reset authorization."""

    password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={
                "id": "reset-password",
                "class": "form-input password-field",
                "placeholder": "Enter your new strong password",
                "autocomplete": "new-password",
                "required": "required",
            }
        ),
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={
                "id": "reset-confirm-password",
                "class": "form-input password-field",
                "placeholder": "Confirm your new password",
                "autocomplete": "new-password",
                "required": "required",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password:
            if password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match. Please verify and re-enter.")
            else:
                errors = PasswordService.validate_password_strength(password)
                if errors:
                    for err in errors:
                        self.add_error("password", err)

        return cleaned_data

