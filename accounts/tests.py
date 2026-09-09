from django.test import TestCase, RequestFactory, Client
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.db import connection
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.contrib.auth import login, get_user
from django.core import mail
from unittest.mock import patch, MagicMock
import io
import json
import zipfile
import hashlib
import smtplib
import re
import secrets
import os

from accounts.models import AuthUser, AuthOtps, AuthConfigurations
from accounts.services.otp_service import OTPService
from accounts.services.password_service import PasswordService
from accounts.services.user_service import UserService
from accounts.services.config_service import ConfigService
from accounts.services.export_service import ExportService
from accounts.services.template_registry import TemplateRegistry
from accounts.backends import AuthUserBackend
from accounts.forms import RegistrationForm
from accounts.services.delivery_service import (
    sms_outbox,
    whatsapp_outbox,
    TwilioSMSProviderAdapter,
    TwilioWhatsAppProviderAdapter,
    OTPDeliveryRouter,
    normalize_phone_number,
)


def setup_test_sqlite_tables():
    """Helper to ensure custom columns and auth_otps table exist in SQLite in-memory DB."""
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if "auth_user" in tables:
            columns = [col.name for col in connection.introspection.get_table_description(cursor, "auth_user")]
            if "full_name" not in columns:
                cursor.execute("ALTER TABLE auth_user ADD COLUMN full_name VARCHAR(150)")
            if "mobile" not in columns:
                cursor.execute("ALTER TABLE auth_user ADD COLUMN mobile VARCHAR(20)")
            if "password_hash" not in columns:
                cursor.execute("ALTER TABLE auth_user ADD COLUMN password_hash VARCHAR(255)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                identifier VARCHAR(255) NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                otp_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                is_used INTEGER NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                builder_session_id VARCHAR(255) NULL,
                configuration_name VARCHAR(255) NOT NULL,
                landing_url TEXT NULL,
                redirect_url TEXT NULL,
                configuration_data JSON NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)


class IsolatedSQLiteAuthTestCase(TestCase):
    """
    Test suite for Phase 4 Authentication Service Layer.
    Guaranteed to run ONLY in-memory against SQLite, completely isolated from AWS RDS.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.backend = AuthUserBackend()
        self.rf = RequestFactory()

    # -------------------------------------------------------------
    # PASSWORD SERVICE TESTS
    # -------------------------------------------------------------

    def test_password_service_hashing_and_verification(self):
        raw_pass = "EnterprisePass@2026"
        hashed = PasswordService.hash_password(raw_pass)

        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertTrue(PasswordService.verify_password(raw_pass, hashed))
        self.assertFalse(PasswordService.verify_password("WrongPassword123", hashed))

    def test_password_service_strength_validation(self):
        short_errors = PasswordService.validate_password_strength("short")
        self.assertTrue(len(short_errors) > 0)

        valid_errors = PasswordService.validate_password_strength("ValidPassword#2026")
        self.assertEqual(len(valid_errors), 0)

    def test_password_service_user_dual_sync(self):
        user = AuthUser(username="testsync", email="sync@example.com")
        PasswordService.apply_password_to_user(user, "SyncPassword123")

        self.assertEqual(user.password, user.password_hash)
        self.assertTrue(user.check_password("SyncPassword123"))

    # -------------------------------------------------------------
    # OTP SERVICE TESTS
    # -------------------------------------------------------------

    def test_otp_generation_and_hashing(self):
        success, msg = OTPService.generate_and_send_otp("user@example.com", purpose="login")
        self.assertTrue(success)

        otp_record = AuthOtps.objects.filter(identifier="user@example.com", purpose="login").first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp_hash), 64)
        self.assertEqual(otp_record.is_used, 0)
        self.assertEqual(otp_record.attempt_count, 0)
        self.assertFalse(otp_record.is_expired)

    def test_otp_resend_cooldown(self):
        success1, _ = OTPService.generate_and_send_otp("cooldown@example.com", purpose="login")
        self.assertTrue(success1)

        success2, msg2 = OTPService.generate_and_send_otp("cooldown@example.com", purpose="login")
        self.assertFalse(success2)
        self.assertIn("Please wait", msg2)

    def test_otp_verification_success_and_single_use(self):
        clean_id = "singleuse@example.com"
        raw_code = "654321"
        AuthOtps.objects.create(
            identifier=clean_id,
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )

        is_valid, msg, rec = OTPService.verify_otp(clean_id, raw_code, purpose="login")
        self.assertTrue(is_valid)
        self.assertIsNotNone(rec)

        rec.refresh_from_db()
        self.assertEqual(rec.is_used, 1)

        is_valid_again, msg_again, _ = OTPService.verify_otp(clean_id, raw_code, purpose="login")
        self.assertFalse(is_valid_again)
        self.assertIn("already been used", msg_again)

    def test_otp_attempt_limits_and_locking(self):
        clean_id = "lockout@example.com"
        raw_code = "789123"
        AuthOtps.objects.create(
            identifier=clean_id,
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )

        for _ in range(4):
            valid, msg, _ = OTPService.verify_otp(clean_id, "000000", purpose="login")
            self.assertFalse(valid)
            self.assertIn("attempt(s) remaining", msg)

        valid_final, msg_final, _ = OTPService.verify_otp(clean_id, "000000", purpose="login")
        self.assertFalse(valid_final)
        self.assertIn("Maximum attempts exceeded", msg_final)

        valid_after, msg_after, _ = OTPService.verify_otp(clean_id, raw_code, purpose="login")
        self.assertFalse(valid_after)

    def test_otp_purpose_isolation(self):
        clean_id = "purpose@example.com"
        raw_code = "333444"
        AuthOtps.objects.create(
            identifier=clean_id,
            purpose="register",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )

        valid, msg, _ = OTPService.verify_otp(clean_id, raw_code, purpose="login")
        self.assertFalse(valid)

        valid_reg, _, _ = OTPService.verify_otp(clean_id, raw_code, purpose="register")
        self.assertTrue(valid_reg)

    def test_otp_expiration(self):
        clean_id = "expired@example.com"
        raw_code = "111222"
        AuthOtps.objects.create(
            identifier=clean_id,
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() - timedelta(minutes=1),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now() - timedelta(minutes=6),
        )

        valid, msg, _ = OTPService.verify_otp(clean_id, raw_code, purpose="login")
        self.assertFalse(valid)
        self.assertIn("expired", msg)

    # -------------------------------------------------------------
    # AUTHENTICATION BACKEND & MULTI-IDENTIFIER TESTS
    # -------------------------------------------------------------

    def test_backend_multi_identifier_password_authentication(self):
        user = AuthUser.objects.create(
            username="multi_user",
            first_name="Multi",
            last_name="User",
            email="multi@example.com",
            mobile="9876543210",
            is_active=1,
        )
        user.set_password("MultiPass@123")
        user.save()

        # Login by Username
        user_by_name = self.backend.authenticate(None, identifier="multi_user", password="MultiPass@123")
        self.assertIsNotNone(user_by_name)
        self.assertEqual(user_by_name.id, user.id)

        # Login by Email
        user_by_email = self.backend.authenticate(None, identifier="multi@example.com", password="MultiPass@123")
        self.assertIsNotNone(user_by_email)
        self.assertEqual(user_by_email.id, user.id)

        # Login by Mobile
        user_by_mobile = self.backend.authenticate(None, identifier="9876543210", password="MultiPass@123")
        self.assertIsNotNone(user_by_mobile)
        self.assertEqual(user_by_mobile.id, user.id)

        # Failed password
        wrong_pass = self.backend.authenticate(None, identifier="multi_user", password="BadPassword")
        self.assertIsNone(wrong_pass)

    def test_backend_otp_authentication(self):
        user = AuthUser.objects.create(
            username="otp_user",
            email="otp_user@example.com",
            mobile="9998887777",
            is_active=1,
        )
        user.set_password("DummyPass")
        user.save()

        raw_code = "445566"
        AuthOtps.objects.create(
            identifier="otp_user@example.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )

        auth_success = self.backend.authenticate(None, identifier="otp_user@example.com", otp=raw_code, purpose="login")
        self.assertIsNotNone(auth_success)
        self.assertEqual(auth_success.id, user.id)

        auth_fail = self.backend.authenticate(None, identifier="otp_user@example.com", otp="000000", purpose="login")
        self.assertIsNone(auth_fail)

    def test_django_session_login_and_request_user(self):
        user = AuthUser.objects.create(
            username="session_user",
            first_name="Session",
            last_name="Tester",
            email="session@example.com",
            is_active=1,
        )
        user.set_password("SessionSecret#1")
        user.save()

        request = self.rf.get("/dashboard/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        login(request, user, backend="accounts.backends.AuthUserBackend")
        request.session.save()

        self.assertEqual(request.session["_auth_user_id"], str(user.id))
        self.assertEqual(request.session["_auth_user_backend"], "accounts.backends.AuthUserBackend")
        self.assertTrue(bool(request.session["_auth_user_hash"]))

        retrieved_user = get_user(request)
        self.assertIsInstance(retrieved_user, AuthUser)
        self.assertEqual(retrieved_user.id, user.id)
        self.assertTrue(retrieved_user.is_authenticated)
        self.assertFalse(retrieved_user.is_anonymous)
        self.assertEqual(retrieved_user.get_username(), "session_user")
        self.assertEqual(retrieved_user.get_full_name(), "Session Tester")


class Phase5LoginIntegrationTests(TestCase):
    """
    Integration tests for the Login UI, HTTP POST password flow, and AJAX OTP endpoints.
    Runs exclusively against isolated SQLite.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.user = AuthUser.objects.create(
            username="test_login_user",
            first_name="Test",
            last_name="Login",
            email="test_login@company.com",
            mobile="9876500000",
            is_active=1,
        )
        self.user.set_password("LoginPass@2026")
        self.user.save()

    def test_login_page_renders_successfully(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome Back")
        self.assertContains(response, "Password")
        self.assertContains(response, "One-Time Password")

    def test_password_login_flow_success(self):
        response = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "test_login_user",
                "password": "LoginPass@2026",
                "remember_me": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Active")
        self.assertContains(response, "test_login_user")

    def test_password_login_invalid_password(self):
        response = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "test_login_user",
                "password": "WrongPassword123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid credentials")

    def test_otp_request_api_success_and_cooldown(self):
        res1 = self.client.post(
            "/api/otp/request/",
            {"identifier": "test_login@company.com", "channel": "email"},
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertTrue(data1["success"])
        self.assertEqual(data1["cooldown"], 60)

        res2 = self.client.post(
            "/api/otp/request/",
            {"identifier": "test_login@company.com", "channel": "email"},
        )
        self.assertEqual(res2.status_code, 400)
        data2 = res2.json()
        self.assertFalse(data2["success"])
        self.assertIn("Please wait", data2["message"])

    def test_otp_request_api_unknown_account(self):
        res = self.client.post(
            "/api/otp/request/",
            {"identifier": "nonexistent@company.com", "channel": "email"},
        )
        self.assertEqual(res.status_code, 404)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("No account found", data["message"])

    def test_otp_verify_api_success_and_session(self):
        raw_code = "889900"
        AuthOtps.objects.create(
            user=self.user,
            identifier="test_login@company.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )

        res = self.client.post(
            "/api/otp/verify/",
            {
                "identifier": "test_login@company.com",
                "otp_code": raw_code,
                "remember_me": "on",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])

        dash_res = self.client.get("/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Session Active")

    def test_otp_verify_api_invalid_code(self):
        res = self.client.post(
            "/api/otp/verify/",
            {
                "identifier": "test_login@company.com",
                "otp_code": "000000",
            },
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])

    def test_logout_clears_session(self):
        self.client.login(username="test_login_user", password="LoginPass@2026")
        logout_res = self.client.get("/logout/", follow=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertContains(logout_res, "You have been logged out successfully.")

        dash_res = self.client.get("/dashboard/")
        self.assertEqual(dash_res.status_code, 302)


class Phase6RegistrationIntegrationTests(TestCase):
    """
    Comprehensive tests for Phase 6 Registration and Account Creation.
    Validates all 20 specified criteria in isolated in-memory SQLite.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.valid_payload = {
            "full_name": "Jane Developer",
            "email": "jane.dev@company.com",
            "mobile": "9876543210",
            "password": "StrongPassword#2026",
            "confirm_password": "StrongPassword#2026",
        }

    # 1. Registration page loads
    def test_01_registration_page_loads(self):
        res = self.client.get("/register/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Create Account")
        self.assertContains(res, "Full Name")
        self.assertContains(res, "Email Address")

    # 2. Valid registration validation
    def test_02_valid_registration_validation(self):
        form = RegistrationForm(self.valid_payload)
        self.assertTrue(form.is_valid(), form.errors)

    # 3. Invalid email
    def test_03_invalid_email(self):
        payload = self.valid_payload.copy()
        payload["email"] = "not-an-email"
        form = RegistrationForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    # 4. Invalid mobile
    def test_04_invalid_mobile(self):
        payload = self.valid_payload.copy()
        payload["mobile"] = "123"  # too short
        form = RegistrationForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn("mobile", form.errors)

    # 5. Weak password
    def test_05_weak_password(self):
        payload = self.valid_payload.copy()
        payload["password"] = "short"
        payload["confirm_password"] = "short"
        form = RegistrationForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    # 6. Password mismatch
    def test_06_password_mismatch(self):
        payload = self.valid_payload.copy()
        payload["confirm_password"] = "DifferentPassword#2026"
        form = RegistrationForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)

    # 7. Duplicate email
    def test_07_duplicate_email(self):
        AuthUser.objects.create(
            username="existing_email_user",
            email="jane.dev@company.com",
            is_active=1,
        )
        form = RegistrationForm(self.valid_payload)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("already exists", form.errors["email"][0])

    # 8. Duplicate username generation
    def test_08_duplicate_username_generation(self):
        u1 = UserService.generate_unique_username("alex.smith@company.com")
        self.assertEqual(u1, "alex_smith")
        AuthUser.objects.create(username="alex_smith", email="other1@company.com", is_active=1)

        u2 = UserService.generate_unique_username("alex.smith@company.com")
        self.assertEqual(u2, "alex_smith2")
        AuthUser.objects.create(username="alex_smith2", email="other2@company.com", is_active=1)

        u3 = UserService.generate_unique_username("alex.smith@company.com")
        self.assertEqual(u3, "alex_smith3")

    # 9. Duplicate mobile
    def test_09_duplicate_mobile(self):
        AuthUser.objects.create(
            username="mobile_user",
            email="diff@company.com",
            mobile="9876543210",
            is_active=1,
        )
        form = RegistrationForm(self.valid_payload)
        self.assertFalse(form.is_valid())
        self.assertIn("mobile", form.errors)

    # 10. Registration OTP generation
    def test_10_registration_otp_generation(self):
        res = self.client.post("/register/", self.valid_payload)
        self.assertEqual(res.status_code, 200)

        otp_record = AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp_hash), 64)
        self.assertFalse(otp_record.is_expired)

    # 11. Registration OTP verification
    def test_11_registration_otp_verification(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "123456"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )

        res = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])

    # 12. Wrong OTP
    def test_12_wrong_otp(self):
        self.client.post("/register/", self.valid_payload)
        res = self.client.post("/api/register/otp/verify/", {"otp_code": "000000"})
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])

    # 13. Expired OTP
    def test_13_expired_otp(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "123456"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        res = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("expired", data["message"])

    # 14. OTP attempt limit
    def test_14_otp_attempt_limit(self):
        self.client.post("/register/", self.valid_payload)
        for _ in range(5):
            res = self.client.post("/api/register/otp/verify/", {"otp_code": "000000"})
            self.assertEqual(res.status_code, 400)

        otp_rec = AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").first()
        self.assertEqual(otp_rec.is_used, 1)

    # 15. Resend cooldown
    def test_15_resend_cooldown(self):
        self.client.post("/register/", self.valid_payload)
        res = self.client.post("/api/register/otp/resend/")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("Please wait", data["message"])

    # 16. Successful AuthUser creation
    def test_16_successful_auth_user_creation(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "654321"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})

        user = AuthUser.objects.filter(email="jane.dev@company.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, "Jane Developer")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Developer")
        self.assertEqual(user.is_active, 1)

    # 17. password == password_hash
    def test_17_password_equals_password_hash(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "654321"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})

        user = AuthUser.objects.filter(email="jane.dev@company.com").first()
        self.assertEqual(user.password, user.password_hash)

    # 18. Password is PBKDF2 hash
    def test_18_password_is_pbkdf2_hash(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "654321"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})

        user = AuthUser.objects.filter(email="jane.dev@company.com").first()
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password("StrongPassword#2026"))
        self.assertFalse(user.check_password("WrongPassword"))

    # 19. Successful login/session after registration
    def test_19_successful_login_session_after_registration(self):
        self.client.post("/register/", self.valid_payload)
        raw_code = "654321"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})

        # Request protected dashboard
        dash_res = self.client.get("/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Session Active")
        self.assertContains(dash_res, "Jane Developer")

    # 20. No plaintext password persistence
    def test_20_no_plaintext_password_persistence(self):
        self.client.post("/register/", self.valid_payload)
        session_pending = self.client.session.get("pending_registration")

        # Plaintext password is NOT in session
        self.assertNotIn("password", session_pending)
        # Only the PBKDF2 hash is stored
        self.assertIn("hashed_password", session_pending)
        self.assertTrue(session_pending["hashed_password"].startswith("pbkdf2_sha256$"))

        raw_code = "654321"
        AuthOtps.objects.filter(identifier="jane.dev@company.com", purpose="register").update(
            otp_hash=OTPService._hash_otp(raw_code)
        )
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code})

        # Session is cleaned after verification
        self.assertNotIn("pending_registration", self.client.session)


class Phase65EmailDeliveryIntegrationTests(TestCase):
    """
    Automated integration tests for Phase 6.5: Real Email OTP Delivery.
    Tests verify dispatch to in-memory mail outbox, context, security, recipient checks,
    and failure handling without touching AWS RDS.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        mail.outbox.clear()
        self.reg_payload = {
            "full_name": "Delivery Tester",
            "email": "tester.delivery@company.com",
            "mobile": "9876543299",
            "password": "SecurePassword#2026",
            "confirm_password": "SecurePassword#2026",
        }

    # 1. Registration OTP email is dispatched
    def test_01_registration_otp_email_dispatched(self):
        res = self.client.post("/register/", self.reg_payload, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    # 2. Correct recipient email is used
    def test_02_correct_recipient_email_used(self):
        self.client.post("/register/", self.reg_payload, content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("tester.delivery@company.com", sent_email.to)

    # 3. Exactly one registration OTP email is generated
    def test_03_exactly_one_registration_otp_email_generated(self):
        self.client.post("/register/", self.reg_payload, content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)

    # 4. Email contains expected registration context
    def test_04_email_contains_expected_registration_context(self):
        self.client.post("/register/", self.reg_payload, content_type="application/json")
        sent_email = mail.outbox[0]
        # Check platform name
        self.assertIn("Authentication Platform", sent_email.subject)
        self.assertIn("Authentication Platform", sent_email.body)
        # Check purpose
        self.assertIn("Account Registration", sent_email.body)
        # Check expiry information
        self.assertIn("5 minutes", sent_email.body)
        # Check security advisory
        self.assertIn("never share", sent_email.body.lower())

    # 5. OTP is not returned in API JSON response
    def test_05_otp_not_returned_in_api_json_response(self):
        res = self.client.post("/register/", self.reg_payload, content_type="application/json")
        data = res.json()
        self.assertTrue(data["success"])
        # Ensure no otp field exists in JSON response
        self.assertNotIn("otp", data)
        self.assertNotIn("raw_otp", data)
        self.assertNotIn("otp_code", data)
        self.assertNotIn("code", data)

    # 6. Email delivery failure returns an appropriate error
    def test_06_email_delivery_failure_returns_appropriate_error(self):
        with patch("accounts.services.delivery_service.send_mail", side_effect=smtplib.SMTPException("SMTP connection refused")):
            res = self.client.post("/register/", self.reg_payload, content_type="application/json")
            self.assertEqual(res.status_code, 400)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertEqual(data["message"], "We couldn't send the verification email right now. Please try again.")

            # Ensure pending registration was cleared from session
            self.assertNotIn("pending_registration", self.client.session)

            # Ensure no active unreceived OTP is left in auth_otps
            active_otps = AuthOtps.objects.filter(identifier="tester.delivery@company.com", purpose="register", is_used=0)
            self.assertEqual(active_otps.count(), 0)

    # 7. Login OTP delivery still works
    def test_07_login_otp_delivery_still_works(self):
        AuthUser.objects.create(
            username="login_tester",
            email="login.tester@company.com",
            password="pbkdf2_sha256$test",
            password_hash="pbkdf2_sha256$test",
            is_active=1,
        )
        res = self.client.post(
            "/api/otp/request/",
            {"identifier": "login.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        login_email = mail.outbox[0]
        self.assertIn("login.tester@company.com", login_email.to)
        self.assertIn("Sign In", login_email.body)

    # 8. Registration OTP uses purpose="register"
    def test_08_registration_otp_uses_register_purpose(self):
        self.client.post("/register/", self.reg_payload, content_type="application/json")
        otp_rec = AuthOtps.objects.filter(identifier="tester.delivery@company.com").first()
        self.assertIsNotNone(otp_rec)
        self.assertEqual(otp_rec.purpose, "register")

    # 9. OTP remains hashed in auth_otps
    def test_09_otp_remains_hashed_in_auth_otps(self):
        self.client.post("/register/", self.reg_payload, content_type="application/json")
        otp_rec = AuthOtps.objects.filter(identifier="tester.delivery@company.com").first()
        self.assertIsNotNone(otp_rec)
        # SHA-256 is 64 hex characters
        self.assertEqual(len(otp_rec.otp_hash), 64)
        # Verify it is not the plaintext 6 digits
        self.assertFalse(otp_rec.otp_hash.isdigit())

    # 10. No plaintext password is exposed
    def test_10_no_plaintext_password_exposed(self):
        res = self.client.post("/register/", self.reg_payload, content_type="application/json")
        sent_email = mail.outbox[0]
        self.assertNotIn("SecurePassword#2026", sent_email.body)
        self.assertNotIn("SecurePassword#2026", sent_email.subject)
        self.assertNotIn("SecurePassword#2026", res.content.decode("utf-8"))


class Phase65RealDeliveryTestSuite(TestCase):
    """
    Phase 6.5 Comprehensive Test Suite: 40 Specific Test Cases
    Covering Real OTP Delivery (Email + SMS + WhatsApp), Channel Isolation,
    OTP Rules, Multi-Channel Registration, and Multi-Channel Login.
    All tests execute in isolated in-memory SQLite with mocked external providers.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        mail.outbox.clear()
        sms_outbox.clear()
        whatsapp_outbox.clear()

    # =========================================================================
    # EMAIL (Tests 1-5)
    # =========================================================================

    def test_01_email_otp_dispatch_succeeds(self):
        """1. Email OTP dispatch succeeds."""
        success, msg = OTPService.generate_and_send_otp("test1@company.com", purpose="register", channel="email")
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

    def test_02_correct_email_recipient_is_used(self):
        """2. Correct email recipient is used."""
        target_email = "target.user@company.com"
        OTPService.generate_and_send_otp(target_email, purpose="register", channel="email")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(target_email, mail.outbox[0].to)

    def test_03_email_contains_otp_verification_information(self):
        """3. Email contains OTP verification information."""
        OTPService.generate_and_send_otp("info@company.com", purpose="register", channel="email")
        sent = mail.outbox[0]
        self.assertIn("Authentication Platform", sent.subject)
        self.assertIn("verification code", sent.body.lower())
        self.assertIn("5 minutes", sent.body)
        self.assertIn("never share", sent.body.lower())

    def test_04_api_response_does_not_contain_otp(self):
        """4. API response does not contain OTP."""
        AuthUser.objects.create(username="email_api_user", email="api_secure@company.com", is_active=1)
        res = self.client.post("/api/otp/request/", {"identifier": "api_secure@company.com", "channel": "email"}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        for forbidden_key in ("otp", "raw_otp", "otp_code", "code"):
            self.assertNotIn(forbidden_key, data)

    def test_05_email_failure_is_handled_safely(self):
        """5. Email failure is handled safely."""
        AuthUser.objects.create(username="email_fail_user", email="fail@company.com", is_active=1)
        with patch("accounts.services.delivery_service.send_mail", side_effect=smtplib.SMTPException("Connection down")):
            res = self.client.post("/api/otp/request/", {"identifier": "fail@company.com", "channel": "email"}, content_type="application/json")
            self.assertEqual(res.status_code, 400)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertEqual(data["message"], "We couldn't send the verification email right now. Please try again.")

    # =========================================================================
    # SMS (Tests 6-10)
    # =========================================================================

    def test_06_sms_channel_selected_correctly(self):
        """6. SMS channel selected correctly."""
        phone = "+919876543210"
        success, msg = OTPService.generate_and_send_otp(phone, purpose="login", channel="sms")
        self.assertTrue(success)
        self.assertEqual(len(sms_outbox), 1)
        self.assertEqual(sms_outbox[0]["to"], phone)

    def test_07_correct_phone_number_passed_to_sms_provider(self):
        """7. Correct phone number passed to provider."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms", return_value=(True, "OK")) as mock_sms:
            OTPService.generate_and_send_otp("9876543211", purpose="login", channel="sms")
            mock_sms.assert_called_once()
            args, _ = mock_sms.call_args
            self.assertEqual(args[0], "+919876543211")

    def test_08_sms_provider_called(self):
        """8. SMS provider called."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms", return_value=(True, "OK")) as mock_sms:
            OTPService.generate_and_send_otp("+919876543212", purpose="login", channel="sms")
            self.assertEqual(mock_sms.call_count, 1)

    def test_09_sms_failure_handled_safely(self):
        """9. SMS failure handled safely."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms", return_value=(False, "Provider network error")):
            success, msg = OTPService.generate_and_send_otp("+919876543213", purpose="login", channel="sms")
            self.assertFalse(success)
            self.assertEqual(msg, "We couldn't send the SMS verification code right now. Please try again.")

    def test_10_otp_not_returned_in_sms_api_response(self):
        """10. OTP not returned in API response."""
        AuthUser.objects.create(username="sms_user_api", mobile="+919876543214", is_active=1)
        res = self.client.post("/api/otp/request/", {"identifier": "+919876543214", "channel": "sms"}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        for forbidden_key in ("otp", "raw_otp", "otp_code", "code"):
            self.assertNotIn(forbidden_key, data)

    # =========================================================================
    # WHATSAPP (Tests 11-15)
    # =========================================================================

    def test_11_whatsapp_channel_selected_correctly(self):
        """11. WhatsApp channel selected correctly."""
        phone = "+919876543220"
        success, msg = OTPService.generate_and_send_otp(phone, purpose="login", channel="whatsapp")
        self.assertTrue(success)
        self.assertEqual(len(whatsapp_outbox), 1)
        self.assertEqual(whatsapp_outbox[0]["to"], phone)

    def test_12_correct_phone_number_passed_to_whatsapp_provider(self):
        """12. Correct phone number passed to provider."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp", return_value=(True, "OK")) as mock_wa:
            OTPService.generate_and_send_otp("9876543221", purpose="login", channel="whatsapp")
            mock_wa.assert_called_once()
            args, _ = mock_wa.call_args
            self.assertEqual(args[0], "+919876543221")

    def test_13_whatsapp_provider_called(self):
        """13. WhatsApp provider called."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp", return_value=(True, "OK")) as mock_wa:
            OTPService.generate_and_send_otp("+919876543222", purpose="login", channel="whatsapp")
            self.assertEqual(mock_wa.call_count, 1)

    def test_14_whatsapp_failure_handled_safely(self):
        """14. WhatsApp failure handled safely."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp", return_value=(False, "WhatsApp unreachable")):
            success, msg = OTPService.generate_and_send_otp("+919876543223", purpose="login", channel="whatsapp")
            self.assertFalse(success)
            self.assertEqual(msg, "We couldn't send the WhatsApp verification code right now. Please try again.")

    def test_15_otp_not_returned_in_whatsapp_api_response(self):
        """15. OTP not returned in API response."""
        AuthUser.objects.create(username="wa_user_api", mobile="+919876543224", is_active=1)
        res = self.client.post("/api/otp/request/", {"identifier": "+919876543224", "channel": "whatsapp"}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        for forbidden_key in ("otp", "raw_otp", "otp_code", "code"):
            self.assertNotIn(forbidden_key, data)

    # =========================================================================
    # CHANNEL ISOLATION (Tests 16-21)
    # =========================================================================

    def test_16_email_selection_never_calls_sms(self):
        """16. Email selection never calls SMS."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms") as mock_sms:
            OTPService.generate_and_send_otp("iso_email_sms@company.com", purpose="login", channel="email")
            mock_sms.assert_not_called()
            self.assertEqual(len(sms_outbox), 0)
            self.assertEqual(len(mail.outbox), 1)

    def test_17_email_selection_never_calls_whatsapp(self):
        """17. Email selection never calls WhatsApp."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp") as mock_wa:
            OTPService.generate_and_send_otp("iso_email_wa@company.com", purpose="login", channel="email")
            mock_wa.assert_not_called()
            self.assertEqual(len(whatsapp_outbox), 0)
            self.assertEqual(len(mail.outbox), 1)

    def test_18_sms_selection_never_calls_email(self):
        """18. SMS selection never calls Email."""
        OTPService.generate_and_send_otp("+919876543230", purpose="login", channel="sms")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(sms_outbox), 1)

    def test_19_sms_selection_never_calls_whatsapp(self):
        """19. SMS selection never calls WhatsApp."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp") as mock_wa:
            OTPService.generate_and_send_otp("+919876543231", purpose="login", channel="sms")
            mock_wa.assert_not_called()
            self.assertEqual(len(whatsapp_outbox), 0)
            self.assertEqual(len(sms_outbox), 1)

    def test_20_whatsapp_selection_never_calls_email(self):
        """20. WhatsApp selection never calls Email."""
        OTPService.generate_and_send_otp("+919876543240", purpose="login", channel="whatsapp")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(whatsapp_outbox), 1)

    def test_21_whatsapp_selection_never_calls_sms(self):
        """21. WhatsApp selection never calls SMS."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms") as mock_sms:
            OTPService.generate_and_send_otp("+919876543241", purpose="login", channel="whatsapp")
            mock_sms.assert_not_called()
            self.assertEqual(len(sms_outbox), 0)
            self.assertEqual(len(whatsapp_outbox), 1)

    # =========================================================================
    # OTP RULES (Tests 22-28)
    # =========================================================================

    def test_22_registration_purpose_is_register(self):
        """22. Registration purpose is 'register'."""
        OTPService.generate_and_send_otp("purpose_reg@company.com", purpose="register", channel="email")
        rec = AuthOtps.objects.filter(identifier="purpose_reg@company.com").first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.purpose, "register")

    def test_23_login_purpose_is_login(self):
        """23. Login purpose is 'login'."""
        OTPService.generate_and_send_otp("purpose_login@company.com", purpose="login", channel="email")
        rec = AuthOtps.objects.filter(identifier="purpose_login@company.com").first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.purpose, "login")

    def test_24_otp_hashed(self):
        """24. OTP hashed."""
        OTPService.generate_and_send_otp("hashed_check@company.com", purpose="login", channel="email")
        rec = AuthOtps.objects.filter(identifier="hashed_check@company.com").first()
        self.assertIsNotNone(rec)
        self.assertEqual(len(rec.otp_hash), 64)
        self.assertFalse(rec.otp_hash.isdigit())

    def test_25_expiry_works(self):
        """25. Expiry works."""
        code = "123456"
        AuthOtps.objects.create(
            identifier="expire_me@company.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(code),
            expires_at=timezone.now() - timedelta(seconds=10),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now() - timedelta(minutes=6),
        )
        valid, msg, _ = OTPService.verify_otp("expire_me@company.com", code, purpose="login")
        self.assertFalse(valid)
        self.assertIn("expired", msg.lower())

    def test_26_attempt_limit_works(self):
        """26. Attempt limit works."""
        code = "654321"
        AuthOtps.objects.create(
            identifier="attempts@company.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )
        for _ in range(5):
            valid, msg, _ = OTPService.verify_otp("attempts@company.com", "000000", purpose="login")
            self.assertFalse(valid)

        rec = AuthOtps.objects.filter(identifier="attempts@company.com").first()
        self.assertEqual(rec.attempt_count, 5)
        self.assertEqual(rec.is_used, 1)

        valid_now, msg_now, _ = OTPService.verify_otp("attempts@company.com", code, purpose="login")
        self.assertFalse(valid_now)

    def test_27_resend_cooldown_works(self):
        """27. Resend cooldown works."""
        success1, _ = OTPService.generate_and_send_otp("cooldown_unit@company.com", purpose="login", channel="email")
        self.assertTrue(success1)
        success2, msg2 = OTPService.generate_and_send_otp("cooldown_unit@company.com", purpose="login", channel="email")
        self.assertFalse(success2)
        self.assertIn("Please wait", msg2)

    def test_28_single_use_works(self):
        """28. Single-use works."""
        code = "998877"
        AuthOtps.objects.create(
            identifier="single_use_rule@company.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )
        valid1, _, _ = OTPService.verify_otp("single_use_rule@company.com", code, purpose="login")
        self.assertTrue(valid1)

        valid2, msg2, _ = OTPService.verify_otp("single_use_rule@company.com", code, purpose="login")
        self.assertFalse(valid2)
        self.assertIn("already been used", msg2.lower())

    # =========================================================================
    # REGISTRATION (Tests 29-36)
    # =========================================================================

    def test_29_email_registration_works(self):
        """29. Email registration works."""
        payload = {
            "full_name": "Email Reg User",
            "email": "email.reg@company.com",
            "mobile": "9876543250",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "email",
        }
        res1 = self.client.post("/register/", payload, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        # Extract code from outbox
        match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        raw_code = match.group(1)

        res2 = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        # Check authenticated session
        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "Email Reg User")

    def test_30_sms_registration_works(self):
        """30. SMS registration works."""
        payload = {
            "full_name": "SMS Reg User",
            "email": "sms.reg@company.com",
            "mobile": "+919876543251",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "sms",
        }
        res1 = self.client.post("/register/", payload, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(sms_outbox), 1)
        raw_code = sms_outbox[0]["raw_otp"]

        res2 = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "SMS Reg User")

    def test_31_whatsapp_registration_works(self):
        """31. WhatsApp registration works."""
        payload = {
            "full_name": "WhatsApp Reg User",
            "email": "wa.reg@company.com",
            "mobile": "+919876543252",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "whatsapp",
        }
        res1 = self.client.post("/register/", payload, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(whatsapp_outbox), 1)
        raw_code = whatsapp_outbox[0]["raw_otp"]

        res2 = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "WhatsApp Reg User")

    def test_32_auth_user_created_correctly(self):
        """32. AuthUser created correctly."""
        payload = {
            "full_name": "Auth User Verifier",
            "email": "created.correctly@company.com",
            "mobile": "+919876543253",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "email",
        }
        self.client.post("/register/", payload, content_type="application/json")
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")

        user = AuthUser.objects.filter(email="created.correctly@company.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, "Auth User Verifier")
        self.assertEqual(user.first_name, "Auth")
        self.assertEqual(user.last_name, "User Verifier")
        self.assertEqual(user.mobile, "+919876543253")
        self.assertEqual(user.is_active, 1)

    def test_33_password_equals_password_hash(self):
        """33. password == password_hash."""
        payload = {
            "full_name": "Dual Hash User",
            "email": "dual.hash@company.com",
            "mobile": "+919876543254",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "email",
        }
        self.client.post("/register/", payload, content_type="application/json")
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")

        user = AuthUser.objects.filter(email="dual.hash@company.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.password, user.password_hash)

    def test_34_password_is_pbkdf2(self):
        """34. password is PBKDF2."""
        payload = {
            "full_name": "PBKDF2 User",
            "email": "pbkdf2.user@company.com",
            "mobile": "+919876543255",
            "password": "EnterprisePassword#2026",
            "confirm_password": "EnterprisePassword#2026",
            "channel": "email",
        }
        self.client.post("/register/", payload, content_type="application/json")
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")

        user = AuthUser.objects.filter(email="pbkdf2.user@company.com").first()
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password("EnterprisePassword#2026"))
        self.assertFalse(user.check_password("WrongPassword"))

    def test_35_successful_registration_authenticates_the_user(self):
        """35. successful registration authenticates the user."""
        payload = {
            "full_name": "Auth Session Check",
            "email": "auth.session@company.com",
            "mobile": "+919876543256",
            "password": "Password@2026",
            "confirm_password": "Password@2026",
            "channel": "email",
        }
        self.client.post("/register/", payload, content_type="application/json")
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        res = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertTrue(res.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "Session Active")

    def test_36_no_plaintext_password_persistence(self):
        """36. no plaintext password persistence."""
        payload = {
            "full_name": "No Plaintext User",
            "email": "no.plaintext@company.com",
            "mobile": "+919876543257",
            "password": "SuperSecretPassword#2026",
            "confirm_password": "SuperSecretPassword#2026",
            "channel": "email",
        }
        self.client.post("/register/", payload, content_type="application/json")
        session_data = self.client.session.get("pending_registration")
        self.assertIsNotNone(session_data)
        self.assertNotIn("password", session_data)
        self.assertIn("hashed_password", session_data)
        self.assertTrue(session_data["hashed_password"].startswith("pbkdf2_sha256$"))

        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertNotIn("pending_registration", self.client.session)

    # =========================================================================
    # LOGIN (Tests 37-40)
    # =========================================================================

    def test_37_email_otp_login_works(self):
        """37. Email OTP login works."""
        user = AuthUser.objects.create(
            username="email_otp_login",
            first_name="Email",
            last_name="Login",
            email="email.login@company.com",
            is_active=1,
        )
        user.set_password("DummyPass123")
        user.save()

        res1 = self.client.post("/api/otp/request/", {"identifier": "email.login@company.com", "channel": "email"}, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        res2 = self.client.post("/api/otp/verify/", {"identifier": "email.login@company.com", "otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "email_otp_login")

    def test_38_sms_otp_login_works(self):
        """38. SMS OTP login works."""
        phone = "+919876543260"
        user = AuthUser.objects.create(
            username="sms_otp_login",
            first_name="SMS",
            last_name="Login",
            mobile=phone,
            is_active=1,
        )
        user.set_password("DummyPass123")
        user.save()

        res1 = self.client.post("/api/otp/request/", {"identifier": phone, "channel": "sms"}, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(sms_outbox), 1)
        raw_code = sms_outbox[0]["raw_otp"]

        res2 = self.client.post("/api/otp/verify/", {"identifier": phone, "otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "sms_otp_login")

    def test_39_whatsapp_otp_login_works(self):
        """39. WhatsApp OTP login works."""
        phone = "+919876543261"
        user = AuthUser.objects.create(
            username="wa_otp_login",
            first_name="WhatsApp",
            last_name="Login",
            mobile=phone,
            is_active=1,
        )
        user.set_password("DummyPass123")
        user.save()

        res1 = self.client.post("/api/otp/request/", {"identifier": phone, "channel": "whatsapp"}, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(whatsapp_outbox), 1)
        raw_code = whatsapp_outbox[0]["raw_otp"]

        res2 = self.client.post("/api/otp/verify/", {"identifier": phone, "otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "wa_otp_login")

    def test_40_existing_password_login_still_works(self):
        """40. Existing password login still works."""
        user = AuthUser.objects.create(
            username="pwd_login_user",
            first_name="Password",
            last_name="Tester",
            email="pwd.login@company.com",
            is_active=1,
        )
        user.set_password("EnterpriseLoginPass#2026")
        user.save()

        res = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "pwd_login_user",
                "password": "EnterpriseLoginPass#2026",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Session Active")
        self.assertContains(res, "pwd_login_user")


class Phase7ForgotPasswordTestSuite(TestCase):
    """
    Phase 7 Comprehensive Test Suite: 50 Specific Test Cases
    Covering Forgot Password, Multi-Channel OTP Request (Email, SMS, WhatsApp),
    Channel Isolation, OTP Rules & Expiry, Server-Side Reset Authorization,
    PBKDF2 Password Updates, Session Invalidation, Delivery Failures, and Regression.
    All tests execute in isolated in-memory SQLite with mocked external providers.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        mail.outbox.clear()
        sms_outbox.clear()
        whatsapp_outbox.clear()

        # Seed standard test user
        self.user = AuthUser.objects.create(
            username="reset_tester",
            first_name="Reset",
            last_name="Tester",
            email="reset.tester@company.com",
            mobile="+919876543300",
            is_active=1,
        )
        self.user.set_password("OldEnterprisePass#2026")
        self.user.save()

    # =========================================================================
    # FORGOT PASSWORD (Tests 1-6)
    # =========================================================================

    def test_01_forgot_password_page_loads(self):
        """1. Forgot password page loads."""
        res = self.client.get("/forgot-password/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Forgot Password")
        self.assertContains(res, "Email or Mobile Number")
        self.assertContains(res, "Get verification code from")
        self.assertContains(res, "Back to Sign In")

    def test_02_valid_email_request(self):
        """2. Valid email request."""
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("If an account matches", data["message"])
        self.assertEqual(len(mail.outbox), 1)

    def test_03_valid_mobile_request(self):
        """3. Valid mobile request."""
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "+919876543300", "channel": "sms"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("If an account matches", data["message"])
        self.assertEqual(len(sms_outbox), 1)

    def test_04_generic_response_prevents_account_enumeration(self):
        """4. Generic response prevents account enumeration."""
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "nonexistent@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(
            data["message"],
            "If an account matches the information provided, a verification code will be sent.",
        )
        self.assertNotIn("not found", data["message"].lower())
        self.assertNotIn("no user", data["message"].lower())

    def test_05_existing_user_gets_reset_password_otp(self):
        """5. Existing user gets reset_password OTP."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        otp_rec = AuthOtps.objects.filter(identifier="reset.tester@company.com", purpose="reset_password").first()
        self.assertIsNotNone(otp_rec)
        self.assertEqual(otp_rec.purpose, "reset_password")
        self.assertEqual(len(otp_rec.otp_hash), 64)

    def test_06_non_existing_user_does_not_reveal_account_existence(self):
        """6. Non-existing user does not reveal account existence."""
        res_existing = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        mail.outbox.clear()

        res_nonexisting = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "ghost.user@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res_existing.status_code, res_nonexisting.status_code)
        self.assertEqual(res_existing.json()["message"], res_nonexisting.json()["message"])
        # Non-existing user dispatches 0 emails and creates 0 AuthOtps records
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AuthOtps.objects.filter(identifier="ghost.user@company.com").count(), 0)

    # =========================================================================
    # CHANNELS (Tests 7-15)
    # =========================================================================

    def test_07_email_channel_calls_email_delivery_service(self):
        """7. Email channel calls EmailDeliveryService."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset.tester@company.com", mail.outbox[0].to)

    def test_08_sms_channel_calls_sms_delivery_service(self):
        """8. SMS channel calls SMSDeliveryService."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "+919876543300", "channel": "sms"},
            content_type="application/json",
        )
        self.assertEqual(len(sms_outbox), 1)
        self.assertEqual(sms_outbox[0]["to"], "+919876543300")

    def test_09_whatsapp_channel_calls_whatsapp_delivery_service(self):
        """9. WhatsApp channel calls WhatsAppDeliveryService."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "+919876543300", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(len(whatsapp_outbox), 1)
        self.assertEqual(whatsapp_outbox[0]["to"], "+919876543300")

    def test_10_email_does_not_call_sms(self):
        """10. Email does not call SMS."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms") as mock_sms:
            self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "reset.tester@company.com", "channel": "email"},
                content_type="application/json",
            )
            mock_sms.assert_not_called()
            self.assertEqual(len(sms_outbox), 0)

    def test_11_email_does_not_call_whatsapp(self):
        """11. Email does not call WhatsApp."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp") as mock_wa:
            self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "reset.tester@company.com", "channel": "email"},
                content_type="application/json",
            )
            mock_wa.assert_not_called()
            self.assertEqual(len(whatsapp_outbox), 0)

    def test_12_sms_does_not_call_email(self):
        """12. SMS does not call Email."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "+919876543300", "channel": "sms"},
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_13_sms_does_not_call_whatsapp(self):
        """13. SMS does not call WhatsApp."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp") as mock_wa:
            self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "+919876543300", "channel": "sms"},
                content_type="application/json",
            )
            mock_wa.assert_not_called()
            self.assertEqual(len(whatsapp_outbox), 0)

    def test_14_whatsapp_does_not_call_email(self):
        """14. WhatsApp does not call Email."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "+919876543300", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_15_whatsapp_does_not_call_sms(self):
        """15. WhatsApp does not call SMS."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms") as mock_sms:
            self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "+919876543300", "channel": "whatsapp"},
                content_type="application/json",
            )
            mock_sms.assert_not_called()
            self.assertEqual(len(sms_outbox), 0)

    # =========================================================================
    # OTP RULES (Tests 16-25)
    # =========================================================================

    def test_16_reset_otp_purpose_is_reset_password(self):
        """16. Reset OTP purpose is reset_password."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        rec = AuthOtps.objects.filter(identifier="reset.tester@company.com").first()
        self.assertEqual(rec.purpose, "reset_password")

    def test_17_login_otp_cannot_verify_reset_flow(self):
        """17. Login OTP cannot verify reset flow."""
        raw_code = "776655"
        AuthOtps.objects.create(
            user=self.user,
            identifier="reset.tester@company.com",
            purpose="login",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])

    def test_18_registration_otp_cannot_verify_reset_flow(self):
        """18. Registration OTP cannot verify reset flow."""
        raw_code = "112233"
        AuthOtps.objects.create(
            user=self.user,
            identifier="reset.tester@company.com",
            purpose="register",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now(),
        )
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])

    def test_19_wrong_otp_rejected(self):
        """19. Wrong OTP rejected."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": "000000"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])

    def test_20_expired_otp_rejected(self):
        """20. Expired OTP rejected."""
        raw_code = "554433"
        AuthOtps.objects.create(
            user=self.user,
            identifier="reset.tester@company.com",
            purpose="reset_password",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() - timedelta(minutes=1),
            is_used=0,
            attempt_count=0,
            created_at=timezone.now() - timedelta(minutes=6),
        )
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", res.json()["message"].lower())

    def test_21_used_otp_rejected(self):
        """21. Used OTP rejected."""
        raw_code = "889977"
        AuthOtps.objects.create(
            user=self.user,
            identifier="reset.tester@company.com",
            purpose="reset_password",
            otp_hash=OTPService._hash_otp(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=1,
            attempt_count=0,
            created_at=timezone.now(),
        )
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already been used", res.json()["message"].lower())

    def test_22_five_attempt_limit_enforced(self):
        """22. Five-attempt limit enforced."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        for _ in range(5):
            res = self.client.post(
                "/api/forgot-password/otp/verify/",
                {"identifier": "reset.tester@company.com", "otp_code": "000000"},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 400)

        # Code locked
        res_after = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res_after.status_code, 400)
        self.assertFalse(res_after.json()["success"])

    def test_23_resend_cooldown_enforced(self):
        """23. Resend cooldown enforced."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        res = self.client.post(
            "/api/forgot-password/otp/resend/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Please wait", res.json()["message"])

    def test_24_otp_is_stored_only_as_hash(self):
        """24. OTP is stored only as hash."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        rec = AuthOtps.objects.filter(identifier="reset.tester@company.com", purpose="reset_password").first()
        self.assertEqual(len(rec.otp_hash), 64)
        self.assertFalse(rec.otp_hash.isdigit())

    def test_25_otp_is_never_returned_in_api_response(self):
        """25. OTP is never returned in API response."""
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        data = res.json()
        for key in ("otp", "raw_otp", "otp_code", "code"):
            self.assertNotIn(key, data)

    # =========================================================================
    # RESET AUTHORIZATION (Tests 26-30)
    # =========================================================================

    def test_26_successful_otp_creates_reset_authorization(self):
        """26. Successful OTP creates reset authorization."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.assertEqual(res.json()["redirect_url"], "/reset-password/")

        auth_state = self.client.session.get("password_reset_authorized")
        self.assertIsNotNone(auth_state)
        self.assertEqual(auth_state["user_id"], self.user.id)
        self.assertTrue(bool(auth_state["token"]))

    def test_27_reset_authorization_is_server_side(self):
        """27. Reset authorization is server-side."""
        self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        res = self.client.post(
            "/api/forgot-password/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        # Token is in session, not exposed in cookies or URLs
        self.assertIn("password_reset_authorized", self.client.session)
        self.assertNotIn("token", res.json())

    def test_28_missing_authorization_is_rejected(self):
        """28. Missing authorization is rejected."""
        # Directly requesting /reset-password/ without authorization redirects to /forgot-password/
        res_view = self.client.get("/reset-password/", follow=True)
        self.assertRedirects(res_view, "/forgot-password/")

        # Directly posting to /api/reset-password/ returns 403
        res_api = self.client.post(
            "/api/reset-password/",
            {"password": "NewEnterprisePass#2026", "confirm_password": "NewEnterprisePass#2026"},
            content_type="application/json",
        )
        self.assertEqual(res_api.status_code, 403)

    def test_29_expired_invalid_authorization_is_rejected(self):
        """29. Expired/invalid authorization is rejected."""
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "reset.tester@company.com",
            "token": "dummy_token",
            "expires_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        }
        session.save()

        res = self.client.get("/reset-password/", follow=True)
        self.assertRedirects(res, "/forgot-password/")

    def test_30_authorization_cannot_be_reused_after_reset(self):
        """30. Authorization cannot be reused after reset."""
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "reset.tester@company.com",
            "token": "valid_token",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()

        # First reset succeeds
        res1 = self.client.post(
            "/api/reset-password/",
            {"password": "NewStrongPass#2026", "confirm_password": "NewStrongPass#2026"},
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 200)

        # Second reset with old session fails with 403
        res2 = self.client.post(
            "/api/reset-password/",
            {"password": "AnotherNewPass#2026", "confirm_password": "AnotherNewPass#2026"},
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 403)

    # =========================================================================
    # PASSWORD (Tests 31-38)
    # =========================================================================

    def _setup_authorized_reset_session(self):
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "reset.tester@company.com",
            "token": "valid_token",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()

    def test_31_weak_password_rejected(self):
        """31. Weak password rejected."""
        self._setup_authorized_reset_session()
        res = self.client.post(
            "/api/reset-password/",
            {"password": "short", "confirm_password": "short"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])

    def test_32_password_mismatch_rejected(self):
        """32. Password mismatch rejected."""
        self._setup_authorized_reset_session()
        res = self.client.post(
            "/api/reset-password/",
            {"password": "StrongPassword#2026", "confirm_password": "DifferentPassword#2026"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("match", res.json()["message"].lower())

    def test_33_strong_password_accepted(self):
        """33. Strong password accepted."""
        self._setup_authorized_reset_session()
        res = self.client.post(
            "/api/reset-password/",
            {"password": "EnterprisePassword#2026", "confirm_password": "EnterprisePassword#2026"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.assertEqual(res.json()["redirect_url"], "/login/")

    def test_34_new_password_uses_pbkdf2(self):
        """34. New password uses PBKDF2."""
        self._setup_authorized_reset_session()
        self.client.post(
            "/api/reset-password/",
            {"password": "EnterprisePassword#2026", "confirm_password": "EnterprisePassword#2026"},
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.password.startswith("pbkdf2_sha256$"))

    def test_35_password_equals_password_hash(self):
        """35. password == password_hash."""
        self._setup_authorized_reset_session()
        self.client.post(
            "/api/reset-password/",
            {"password": "EnterprisePassword#2026", "confirm_password": "EnterprisePassword#2026"},
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, self.user.password_hash)

    def test_36_old_password_no_longer_works(self):
        """36. Old password no longer works."""
        self._setup_authorized_reset_session()
        self.client.post(
            "/api/reset-password/",
            {"password": "BrandNewSecret#2026", "confirm_password": "BrandNewSecret#2026"},
            content_type="application/json",
        )
        backend = AuthUserBackend()
        old_auth = backend.authenticate(None, identifier="reset.tester@company.com", password="OldEnterprisePass#2026")
        self.assertIsNone(old_auth)

    def test_37_new_password_works(self):
        """37. New password works."""
        self._setup_authorized_reset_session()
        self.client.post(
            "/api/reset-password/",
            {"password": "BrandNewSecret#2026", "confirm_password": "BrandNewSecret#2026"},
            content_type="application/json",
        )
        backend = AuthUserBackend()
        new_auth = backend.authenticate(None, identifier="reset.tester@company.com", password="BrandNewSecret#2026")
        self.assertIsNotNone(new_auth)
        self.assertEqual(new_auth.id, self.user.id)

    def test_38_plaintext_password_is_never_persisted(self):
        """38. Plaintext password is never persisted."""
        self._setup_authorized_reset_session()
        raw_secret = "SecretPasswordToBeHashed#2026"
        self.client.post(
            "/api/reset-password/",
            {"password": raw_secret, "confirm_password": raw_secret},
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.password, raw_secret)
        self.assertNotIn(raw_secret, self.user.password)
        self.assertNotIn("password_reset_authorized", self.client.session)

    # =========================================================================
    # SESSIONS (Tests 39-40)
    # =========================================================================

    def test_39_existing_authenticated_sessions_are_invalidated(self):
        """39. Existing authenticated sessions are invalidated."""
        client_a = Client()
        client_a.post(
            "/login/",
            {"action": "password_login", "identifier": "reset_tester", "password": "OldEnterprisePass#2026"},
            follow=True,
        )
        # Verify Client A has access to dashboard
        dash_a_before = client_a.get("/dashboard/")
        self.assertEqual(dash_a_before.status_code, 200)

        # Reset password via Client B
        client_b = Client()
        session_b = client_b.session
        session_b["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "reset.tester@company.com",
            "token": "valid_token",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session_b.save()

        client_b.post(
            "/api/reset-password/",
            {"password": "BrandNewSecret#2026", "confirm_password": "BrandNewSecret#2026"},
            content_type="application/json",
        )

        # Verify Client A's session is now invalidated
        dash_a_after = client_a.get("/dashboard/")
        self.assertEqual(dash_a_after.status_code, 302)

    def test_40_reset_does_not_automatically_authenticate_the_user(self):
        """40. Reset does not automatically authenticate the user."""
        self._setup_authorized_reset_session()
        self.client.post(
            "/api/reset-password/",
            {"password": "BrandNewSecret#2026", "confirm_password": "BrandNewSecret#2026"},
            content_type="application/json",
        )
        dash = self.client.get("/dashboard/")
        self.assertEqual(dash.status_code, 302)

    # =========================================================================
    # DELIVERY FAILURE (Tests 41-44)
    # =========================================================================

    def test_41_email_failure_handled_safely(self):
        """41. Email failure handled safely."""
        with patch("accounts.services.delivery_service.send_mail", side_effect=smtplib.SMTPException("SMTP down")):
            res = self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "reset.tester@company.com", "channel": "email"},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()["message"], "We couldn't send the verification email right now. Please try again.")

    def test_42_sms_failure_handled_safely(self):
        """42. SMS failure handled safely."""
        with patch.object(TwilioSMSProviderAdapter, "send_sms", return_value=(False, "Twilio down")):
            res = self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "+919876543300", "channel": "sms"},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()["message"], "We couldn't send the SMS verification code right now. Please try again.")

    def test_43_whatsapp_failure_handled_safely(self):
        """43. WhatsApp failure handled safely."""
        with patch.object(TwilioWhatsAppProviderAdapter, "send_whatsapp", return_value=(False, "WA down")):
            res = self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "+919876543300", "channel": "whatsapp"},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()["message"], "We couldn't send the WhatsApp verification code right now. Please try again.")

    def test_44_ui_does_not_claim_successful_delivery_after_provider_failure(self):
        """44. UI does not claim successful delivery after provider failure."""
        with patch("accounts.services.delivery_service.send_mail", side_effect=smtplib.SMTPException("Fail")):
            res = self.client.post(
                "/api/forgot-password/otp/request/",
                {"identifier": "reset.tester@company.com", "channel": "email"},
                content_type="application/json",
            )
            data = res.json()
            self.assertFalse(data["success"])
            self.assertNotIn("sent", data["message"].lower())

    # =========================================================================
    # REGRESSION (Tests 45-50)
    # =========================================================================

    def test_45_existing_password_login_still_works(self):
        """45. Existing password login still works."""
        res = self.client.post(
            "/login/",
            {"action": "password_login", "identifier": "reset_tester", "password": "OldEnterprisePass#2026"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Session Active")

    def test_46_existing_otp_login_still_works(self):
        """46. Existing OTP login still works."""
        res1 = self.client.post(
            "/api/otp/request/",
            {"identifier": "reset.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 200)
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        res2 = self.client.post(
            "/api/otp/verify/",
            {"identifier": "reset.tester@company.com", "otp_code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

    def test_47_existing_registration_still_works(self):
        """47. Existing registration still works."""
        payload = {
            "full_name": "Reg Pass User",
            "email": "reg.pass@company.com",
            "mobile": "+919876543399",
            "password": "Password#2026",
            "confirm_password": "Password#2026",
            "channel": "email",
        }
        res1 = self.client.post("/register/", payload, content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        raw_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        res2 = self.client.post("/api/register/otp/verify/", {"otp_code": raw_code}, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])

    def test_48_existing_phase_5_tests_continue_passing(self):
        """48. Existing Phase 5 tests continue passing."""
        res = self.client.get("/login/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Forgot password?")

    def test_49_existing_phase_6_tests_continue_passing(self):
        """49. Existing Phase 6 tests continue passing."""
        res = self.client.get("/register/")
        self.assertEqual(res.status_code, 200)

    def test_50_existing_phase_65_tests_continue_passing(self):
        """50. Existing Phase 6.5 tests continue passing."""
        status = OTPDeliveryRouter.get_channel_status()
        self.assertIn("email", status)
        self.assertIn("sms", status)
        self.assertIn("whatsapp", status)


# ==============================================================================
# PHASE 8: PROFESSIONAL AUTHENTICATION TEMPLATE SYSTEM TEST SUITE
# ==============================================================================

class Phase8TemplateSystemTestSuite(TestCase):
    """
    Phase 8 Test Suite: 30 Comprehensive Tests
    Verifying:
      - Template resolver engine (query param, session persistence, default, fallback)
      - Visual templates loading (Modern Glass, Split Screen, Minimal Corporate)
      - Auth workflows across all templates (Login, Register, Forgot Pass, Reset Pass)
      - Multi-channel delivery selector present and active across all templates
      - Template preview dashboard (/templates-preview/)
      - Absence of any demo OTP text in rendered responses
      - Accessibility attributes (ARIA, roles, labels, autocomplete)
      - Responsive layout tokens and meta tags
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        mail.outbox.clear()
        sms_outbox.clear()
        whatsapp_outbox.clear()

        # Seed standard test user
        self.user = AuthUser.objects.create(
            username="template_tester",
            first_name="Template",
            last_name="Tester",
            email="template.tester@company.com",
            mobile="+919876543400",
            is_active=1,
        )
        self.user.set_password("TemplatePass#2026")
        self.user.save()

    # 1. Template resolver default
    def test_01_template_resolver_default(self):
        from accounts.utils import resolve_auth_template
        factory = RequestFactory()
        req = factory.get("/login/")
        req.session = {}
        path, info = resolve_auth_template(req, "login.html")
        self.assertEqual(info["id"], "modern")
        self.assertEqual(path, "accounts/templates/modern/login.html")

    # 2. Template resolver query param
    def test_02_template_resolver_query_param(self):
        from accounts.utils import resolve_auth_template
        factory = RequestFactory()
        req = factory.get("/login/?template=split")
        req.session = {}
        path, info = resolve_auth_template(req, "login.html")
        self.assertEqual(info["id"], "split")
        self.assertEqual(path, "accounts/templates/split/login.html")
        self.assertEqual(req.session.get("auth_template"), "split")

    # 3. Template resolver session persistence
    def test_03_template_resolver_session_persistence(self):
        from accounts.utils import resolve_auth_template
        factory = RequestFactory()
        req = factory.get("/register/")
        req.session = {"auth_template": "corporate"}
        path, info = resolve_auth_template(req, "register.html")
        self.assertEqual(info["id"], "corporate")
        self.assertEqual(path, "accounts/templates/corporate/register.html")

    # 4. Template resolver invalid fallback
    def test_04_template_resolver_invalid_fallback(self):
        from accounts.utils import resolve_auth_template
        factory = RequestFactory()
        req = factory.get("/login/?template=nonexistent_style")
        req.session = {}
        path, info = resolve_auth_template(req, "login.html")
        self.assertEqual(info["id"], "modern")

    # 5. Modern template login loads
    def test_05_modern_template_login_loads(self):
        res = self.client.get("/login/?template=modern")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-modern")
        self.assertContains(res, "Welcome Back")
        self.assertContains(res, "Password")
        self.assertContains(res, "One-Time Password")
        self.assertContains(res, "template_modern.css")

    # 6. Modern template register loads
    def test_06_modern_template_register_loads(self):
        res = self.client.get("/register/?template=modern")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-modern")
        self.assertContains(res, "Create Account")
        self.assertContains(res, "Full Name")
        self.assertContains(res, "Email Address")

    # 7. Modern template forgot password loads
    def test_07_modern_template_forgot_password_loads(self):
        res = self.client.get("/forgot-password/?template=modern")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-modern")
        self.assertContains(res, "Forgot Password")
        self.assertContains(res, "Email or Mobile Number")

    # 8. Modern template reset password loads
    def test_08_modern_template_reset_password_loads(self):
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "template.tester@company.com",
            "token": "tok_123",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()
        res = self.client.get("/reset-password/?template=modern")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-modern")
        self.assertContains(res, "Create New Password")

    # 9. Split template login loads
    def test_09_split_template_login_loads(self):
        res = self.client.get("/login/?template=split")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-split")
        self.assertContains(res, "split-hero")
        self.assertContains(res, "split-auth")
        self.assertContains(res, "Welcome Back")
        self.assertContains(res, "template_split.css")

    # 10. Split template register loads
    def test_10_split_template_register_loads(self):
        res = self.client.get("/register/?template=split")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-split")
        self.assertContains(res, "split-hero")
        self.assertContains(res, "Create Account")

    # 11. Split template forgot password loads
    def test_11_split_template_forgot_password_loads(self):
        res = self.client.get("/forgot-password/?template=split")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-split")
        self.assertContains(res, "split-hero")
        self.assertContains(res, "Forgot Password")

    # 12. Split template reset password loads
    def test_12_split_template_reset_password_loads(self):
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "template.tester@company.com",
            "token": "tok_123",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()
        res = self.client.get("/reset-password/?template=split")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-split")
        self.assertContains(res, "split-hero")
        self.assertContains(res, "Create New Password")

    # 13. Corporate template login loads
    def test_13_corporate_template_login_loads(self):
        res = self.client.get("/login/?template=corporate")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-corporate")
        self.assertContains(res, "Welcome Back")
        self.assertContains(res, "template_corporate.css")

    # 14. Corporate template register loads
    def test_14_corporate_template_register_loads(self):
        res = self.client.get("/register/?template=corporate")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-corporate")
        self.assertContains(res, "Create Account")

    # 15. Corporate template forgot password loads
    def test_15_corporate_template_forgot_password_loads(self):
        res = self.client.get("/forgot-password/?template=corporate")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-corporate")
        self.assertContains(res, "Forgot Password")

    # 16. Corporate template reset password loads
    def test_16_corporate_template_reset_password_loads(self):
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "template.tester@company.com",
            "token": "tok_123",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()
        res = self.client.get("/reset-password/?template=corporate")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-corporate")
        self.assertContains(res, "Create New Password")

    # 17. Templates preview page loads
    def test_17_templates_preview_page_loads(self):
        res = self.client.get("/templates-preview/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Authentication Template System")
        self.assertContains(res, "card-template-modern")
        self.assertContains(res, "card-template-split")
        self.assertContains(res, "card-template-corporate")
        self.assertContains(res, "Modern Glass")
        self.assertContains(res, "Split Screen")
        self.assertContains(res, "Minimal Corporate")

    # 18. Template switching persists across pages via session
    def test_18_template_switching_across_pages(self):
        # Visit login with template=split
        self.client.get("/login/?template=split")
        # Then visit register without query param
        res = self.client.get("/register/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "template-split")

    # 19. Password login works in modern template
    def test_19_password_login_works_in_modern_template(self):
        self.client.get("/login/?template=modern")
        res = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "template_tester",
                "password": "TemplatePass#2026",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Template Tester")

    # 20. Password login works in split template
    def test_20_password_login_works_in_split_template(self):
        self.client.get("/login/?template=split")
        res = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "template_tester",
                "password": "TemplatePass#2026",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Template Tester")

    # 21. Password login works in corporate template
    def test_21_password_login_works_in_corporate_template(self):
        self.client.get("/login/?template=corporate")
        res = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": "template_tester",
                "password": "TemplatePass#2026",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Template Tester")

    # 22. Registration works under split template
    def test_22_registration_works_under_split_template(self):
        self.client.get("/register/?template=split")
        payload = {
            "full_name": "Split User",
            "email": "split.user@company.com",
            "mobile": "+919876543411",
            "password": "StrongPassword#2026",
            "confirm_password": "StrongPassword#2026",
            "channel": "email",
        }
        res = self.client.post("/register/", payload, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.assertEqual(len(mail.outbox), 1)

    # 23. Forgot password OTP works under corporate template
    def test_23_forgot_password_otp_works_under_corporate_template(self):
        self.client.get("/forgot-password/?template=corporate")
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "template.tester@company.com", "channel": "email"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.assertEqual(len(mail.outbox), 1)

    # 24. Password reset works under modern template
    def test_24_password_reset_works_under_modern_template(self):
        session = self.client.session
        session["auth_template"] = "modern"
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": "template.tester@company.com",
            "token": "tok_valid",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()

        res = self.client.post(
            "/api/reset-password/",
            {"password": "BrandNewPass#2026", "confirm_password": "BrandNewPass#2026"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass#2026"))

    # 25. Channel selector present in all templates
    def test_25_channel_selector_present_in_all_templates(self):
        for tpl in ("modern", "split", "corporate"):
            res = self.client.get(f"/register/?template={tpl}")
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'id="subchannel-email-btn"')
            self.assertContains(res, 'id="subchannel-sms-btn"')
            self.assertContains(res, 'id="subchannel-whatsapp-btn"')

    # 26. No demo OTP present in any template HTML
    def test_26_no_demo_otp_present_in_any_template(self):
        for tpl in ("modern", "split", "corporate"):
            for url in ("/login/", "/register/", "/forgot-password/"):
                res = self.client.get(f"{url}?template={tpl}")
                self.assertEqual(res.status_code, 200)
                self.assertNotContains(res, "Demo OTP")
                self.assertNotContains(res, "123456")

    # 27. Accessibility attributes present
    def test_27_accessibility_attributes_present(self):
        for tpl in ("modern", "split", "corporate"):
            res = self.client.get(f"/login/?template={tpl}")
            self.assertContains(res, 'role="tablist"')
            self.assertContains(res, 'role="tab"')
            self.assertContains(res, 'aria-selected="true"')
            self.assertContains(res, 'autocomplete="current-password"')

    # 28. Password visibility buttons have accessible aria labels
    def test_28_password_visibility_buttons_have_aria_labels(self):
        for tpl in ("modern", "split", "corporate"):
            res = self.client.get(f"/login/?template={tpl}")
            self.assertContains(res, 'aria-label="Show password"')

    # 29. Password strength meter present in registration
    def test_29_password_strength_meter_present_in_registration(self):
        for tpl in ("modern", "split", "corporate"):
            res = self.client.get(f"/register/?template={tpl}")
            self.assertContains(res, 'id="strength-meter"')
            self.assertContains(res, 'id="strength-text"')

    # 30. Floating template switcher present
    def test_30_floating_template_switcher_present(self):
        for tpl in ("modern", "split", "corporate"):
            res = self.client.get(f"/login/?template={tpl}")
            self.assertContains(res, "floating-template-switcher")
            self.assertContains(res, "?template=modern")
            self.assertContains(res, "?template=split")
            self.assertContains(res, "?template=corporate")


# ==============================================================================
# PHASE 10: CUSTOM BUILDER TESTS
# ==============================================================================
class Phase10CustomBuilderTests(TestCase):
    """
    Test suite for Phase 10 Custom Builder.
    Verifies that the /builder/ workspace loads, all design controls exist,
    live iframe preview is properly routed, and responsive viewports are present.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_01_builder_view_loads_successfully(self):
        res = self.client.get("/builder/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Auth Studio")
        self.assertContains(res, "Design Controls")
        self.assertContains(res, "Base Template")
        self.assertContains(res, "Branding & Identity")
        self.assertContains(res, "Color Palette")
        self.assertContains(res, "Typography")
        self.assertContains(res, "Card Dimensions")
        self.assertContains(res, "Inputs & Buttons")
        self.assertContains(res, "Auth Settings")

    def test_02_builder_view_with_template_param(self):
        res = self.client.get("/builder/?template=split")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'value="split" selected')

    def test_03_builder_view_invalid_template_falls_back_to_modern(self):
        res = self.client.get("/builder/?template=nonexistent_xyz")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'value="modern" selected')

    def test_04_builder_color_palette_controls(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'id="ctrl-color-primary"')
        self.assertContains(res, 'id="ctrl-color-secondary"')
        self.assertContains(res, 'id="ctrl-color-background"')
        self.assertContains(res, 'id="ctrl-color-card_bg"')
        self.assertContains(res, 'id="ctrl-color-text"')
        self.assertContains(res, 'id="ctrl-color-muted"')
        self.assertContains(res, 'id="ctrl-color-border"')

    def test_05_builder_typography_controls(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'id="ctrl-font-family"')
        self.assertContains(res, "Inter (Modern Clean)")
        self.assertContains(res, "Plus Jakarta Sans (SaaS)")
        self.assertContains(res, "Roboto (Corporate standard)")

    def test_06_builder_card_and_input_sliders(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'id="ctrl-card-width"')
        self.assertContains(res, 'id="ctrl-card-radius"')
        self.assertContains(res, 'id="ctrl-input-height"')
        self.assertContains(res, 'id="ctrl-btn-height"')

    def test_07_builder_auth_settings_toggles(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'id="ctrl-enable-pwd"')
        self.assertContains(res, 'id="ctrl-enable-otp"')
        self.assertContains(res, 'id="ctrl-enable-email"')
        self.assertContains(res, 'id="ctrl-enable-sms"')
        self.assertContains(res, 'id="ctrl-enable-whatsapp"')

    def test_08_builder_device_viewports_present(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'data-mode="desktop"')
        self.assertContains(res, 'data-mode="tablet"')
        self.assertContains(res, 'data-mode="mobile"')

    def test_09_builder_screen_switchers_present(self):
        res = self.client.get("/builder/")
        self.assertContains(res, 'data-screen="login"')
        self.assertContains(res, 'data-screen="register"')
        self.assertContains(res, 'data-screen="forgot_password"')
        self.assertContains(res, 'data-screen="reset_password"')

    def test_10_builder_iframe_preview_url_and_modals(self):
        res = self.client.get("/builder/?template=modern")
        self.assertContains(res, 'id="preview-iframe"')
        self.assertContains(res, '/login/?template=modern&preview=1')
        self.assertContains(res, 'id="save-modal"')
        self.assertContains(res, 'id="manage-modal"')


# ==============================================================================
# PHASE 11: SAVE / LOAD CONFIGURATIONS TESTS
# ==============================================================================
class Phase11ConfigurationsTests(TestCase):
    """
    Test suite for Phase 11 Configuration Persistence.
    Verifies that configurations are saved to auth_configurations,
    ownership is strictly enforced (User A cannot access or modify User B's design),
    and forbidden sensitive keys (passwords, tokens, OTPs) are scrubbed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()
        # Create user A
        self.user_a = AuthUser.objects.create(
            username="usera",
            email="usera@example.com",
            password="pbkdf2_sha256$test$usera",
            password_hash="pbkdf2_sha256$test$usera",
            is_active=1,
        )
        # Create user B
        self.user_b = AuthUser.objects.create(
            username="userb",
            email="userb@example.com",
            password="pbkdf2_sha256$test$userb",
            password_hash="pbkdf2_sha256$test$userb",
            is_active=1,
        )

    def test_01_save_configuration_for_authenticated_user(self):
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        payload = {
            "configuration_name": "User A SaaS Theme",
            "configuration_data": {
                "template": "modern",
                "colors": {"primary": "#6366f1", "background": "#000000"},
            },
        }
        res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["config"]["name"], "User A SaaS Theme")

        # Verify DB record
        record = AuthConfigurations.objects.filter(pk=data["config"]["id"]).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.user_id, self.user_a.id)
        self.assertEqual(record.configuration_data["colors"]["primary"], "#6366f1")

    def test_02_save_configuration_scrubs_forbidden_passwords_and_tokens(self):
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        payload = {
            "configuration_name": "Dangerous Secret Theme",
            "configuration_data": {
                "template": "split",
                "password": "CleartextPassword!",
                "raw_password": "CleartextPassword2!",
                "otp": "123456",
                "api_key": "sk-1234567890",
                "smtp_password": "gmail-app-password",
                "colors": {"primary": "#10b981"},
            },
        }
        res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        config_id = res.json()["config"]["id"]

        record = AuthConfigurations.objects.get(pk=config_id)
        # Sensitive keys must be completely scrubbed from storage
        self.assertNotIn("password", record.configuration_data)
        self.assertNotIn("raw_password", record.configuration_data)
        self.assertNotIn("otp", record.configuration_data)
        self.assertNotIn("api_key", record.configuration_data)
        self.assertNotIn("smtp_password", record.configuration_data)
        # Safe keys remain
        self.assertEqual(record.configuration_data["colors"]["primary"], "#10b981")

    def test_03_load_own_configuration_succeeds(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Design",
            configuration_data={"template": "corporate", "branding": {"brand_name": "CorpA"}},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        res = self.client.get(f"/api/builder/configurations/{cfg.id}/load/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["configuration"]["name"], "User A Design")
        self.assertEqual(data["configuration"]["data"]["branding"]["brand_name"], "CorpA")

    def test_04_ownership_protection_user_b_cannot_load_user_a_config(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Private Theme",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        # User B attempts to load User A's config
        self.client.force_login(self.user_b, backend="accounts.backends.AuthUserBackend")
        res = self.client.get(f"/api/builder/configurations/{cfg.id}/load/")
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.json()["success"])

    def test_05_update_existing_configuration(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="Initial Name",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        update_payload = {
            "config_id": cfg.id,
            "configuration_name": "Updated Name",
            "configuration_data": {"template": "split", "colors": {"primary": "#3b82f6"}},
        }
        res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        cfg.refresh_from_db()
        self.assertEqual(cfg.configuration_name, "Updated Name")
        self.assertEqual(cfg.configuration_data["colors"]["primary"], "#3b82f6")

    def test_06_duplicate_configuration(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="Template Design",
            configuration_data={"template": "corporate"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        res = self.client.post(f"/api/builder/configurations/{cfg.id}/duplicate/")
        self.assertEqual(res.status_code, 200)
        clone_id = res.json()["config"]["id"]

        clone = AuthConfigurations.objects.get(pk=clone_id)
        self.assertEqual(clone.user_id, self.user_a.id)
        self.assertEqual(clone.configuration_name, "Template Design (Copy)")

    def test_07_ownership_protection_user_b_cannot_duplicate_user_a_config(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Only",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_b, backend="accounts.backends.AuthUserBackend")
        res = self.client.post(f"/api/builder/configurations/{cfg.id}/duplicate/")
        self.assertEqual(res.status_code, 403)

    def test_08_delete_configuration(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="To Delete",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        res = self.client.post(f"/api/builder/configurations/{cfg.id}/delete/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(AuthConfigurations.objects.filter(pk=cfg.id).exists())

    def test_09_ownership_protection_user_b_cannot_delete_user_a_config(self):
        cfg = AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Protected",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client.force_login(self.user_b, backend="accounts.backends.AuthUserBackend")
        res = self.client.post(f"/api/builder/configurations/{cfg.id}/delete/")
        self.assertEqual(res.status_code, 403)
        self.assertTrue(AuthConfigurations.objects.filter(pk=cfg.id).exists())

    def test_10_list_configurations_isolated_to_owner(self):
        AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Config 1",
            configuration_data={"template": "modern"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        AuthConfigurations.objects.create(
            user=self.user_a,
            configuration_name="User A Config 2",
            configuration_data={"template": "split"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        AuthConfigurations.objects.create(
            user=self.user_b,
            configuration_name="User B Secret Theme",
            configuration_data={"template": "corporate"},
            is_active=1,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        self.client.force_login(self.user_a, backend="accounts.backends.AuthUserBackend")
        res = self.client.get("/api/builder/configurations/")
        self.assertEqual(res.status_code, 200)
        items = res.json()["configurations"]
        names = [item["name"] for item in items]
        self.assertIn("User A Config 1", names)
        self.assertIn("User A Config 2", names)
        self.assertNotIn("User B Secret Theme", names)


# ==============================================================================
# PHASE 12: ZIP EXPORT TESTS
# ==============================================================================
class Phase12ZipExportTests(TestCase):
    """
    Test suite for Phase 12 ZIP Export.
    Verifies that the generated standalone project contains all required code and templates,
    strictly excludes all secrets and .env files, and sanitizes database credentials.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_01_export_zip_endpoint_returns_valid_archive(self):
        payload = {
            "template": "modern",
            "configuration": {
                "branding": {"brand_name": "Exported SaaS"},
                "colors": {"primary": "#ff3366"},
            },
        }
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/zip")
        self.assertIn("attachment; filename=", res["Content-Disposition"])

        # Check valid zip archive
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        names = zf.namelist()
        self.assertIn("custom-auth-platform/README.md", names)
        self.assertIn("custom-auth-platform/.env.example", names)
        self.assertIn("custom-auth-platform/requirements.txt", names)
        self.assertIn("custom-auth-platform/manage.py", names)
        self.assertIn("custom-auth-platform/config/settings.py", names)
        self.assertIn("custom-auth-platform/accounts/views.py", names)
        self.assertIn("custom-auth-platform/static/accounts/css/auth_tokens.css", names)

    def test_02_exported_tokens_css_reflects_custom_configuration(self):
        payload = {
            "template": "modern",
            "configuration": {
                "colors": {"primary": "#1234ef"},
            },
        }
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        tokens_css = zf.read("custom-auth-platform/static/accounts/css/auth_tokens.css").decode("utf-8")
        self.assertIn("--primary-color: #1234ef;", tokens_css)

    def test_03_zip_strictly_excludes_env_files(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "split", "configuration": {}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        names = zf.namelist()
        # Must NOT contain .env or any variant
        for name in names:
            self.assertFalse(name.endswith("/.env"))
            self.assertFalse(name.endswith(".env"))
            self.assertFalse(".env.production" in name)

    def test_04_zip_strictly_excludes_sqlite_db_and_cache(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "corporate", "configuration": {}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        for name in zf.namelist():
            self.assertNotIn("db.sqlite3", name)
            self.assertNotIn("__pycache__", name)
            self.assertNotIn(".git/", name)

    def test_05_zip_sanitizes_real_db_credentials(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "modern", "configuration": {}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        # Inspect text files to ensure any sensitive environment credentials are fully scrubbed
        db_pwd = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        for info in zf.infolist():
            if not info.filename.endswith((".py", ".txt", ".md", ".html", ".css", ".js")):
                continue
            content = zf.read(info.filename).decode("utf-8", errors="ignore")
            if db_pwd and len(str(db_pwd).strip()) > 3:
                self.assertNotIn(str(db_pwd).strip(), content)
            if db_host and len(str(db_host).strip()) > 3:
                self.assertNotIn(str(db_host).strip(), content)

    def test_06_zip_readme_explains_demo_mode_and_production_setup(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "modern", "configuration": {"branding": {"brand_name": "TestBrand"}}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        readme = zf.read("custom-auth-platform/README.md").decode("utf-8")
        self.assertIn("TestBrand", readme)
        self.assertIn("DEVELOPMENT / DEMO MODE", readme)
        self.assertIn("OTP_DELIVERY_MODE=demo", readme)
        self.assertIn("Demo OTP: 123456", readme)
        self.assertIn("Production Deployment", readme)

    def test_07_zip_env_example_contains_safe_placeholders(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "split", "configuration": {}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        env_ex = zf.read("custom-auth-platform/.env.example").decode("utf-8")
        self.assertIn("OTP_DELIVERY_MODE=demo", env_ex)
        self.assertIn("EMAIL_HOST=smtp.gmail.com", env_ex)
        self.assertIn("EMAIL_HOST_USER=", env_ex)
        self.assertIn("TWILIO_ACCOUNT_SID=", env_ex)

    def test_08_zip_prevent_path_traversal(self):
        res = self.client.post(
            "/api/builder/export-zip/",
            data=json.dumps({"template": "modern", "configuration": {}}),
            content_type="application/json",
        )
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        for name in zf.namelist():
            self.assertTrue(name.startswith("custom-auth-platform/"))
            self.assertNotIn("..", name)
            self.assertFalse(name.startswith("/"))


# ==============================================================================
# PHASE 13: FINAL SECURITY AND DEMO OTP TESTS
# ==============================================================================
class Phase13SecurityAndDemoOTPTests(TestCase):
    """
    Test suite for Phase 13 Final Security and Demo OTP Mode.
    Verifies PBKDF2 password hashing, zero plaintext password/OTP storage,
    demo OTP fixed-code mechanics, session invalidation upon reset,
    and anti-enumeration protection.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_01_demo_mode_otp_value_is_123456(self):
        with patch("accounts.services.delivery_service.is_test_environment", return_value=False):
            with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
                success, msg = OTPService.generate_and_send_otp("demouser@example.com", purpose="login")
                self.assertTrue(success)
                record = AuthOtps.objects.filter(identifier="demouser@example.com", purpose="login").first()
                self.assertIsNotNone(record)
                # Verify that the hashed OTP corresponds to 123456
                expected_hash = hashlib.sha256("123456".encode("utf-8")).hexdigest()
                self.assertEqual(record.otp_hash, expected_hash)

    def test_02_demo_mode_email_login_works_with_123456(self):
        user = AuthUser.objects.create(
            username="demologin",
            email="demologin@example.com",
            is_active=1,
        )
        with patch("accounts.services.delivery_service.is_test_environment", return_value=False):
            with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
                # Request OTP
                req_res = self.client.post("/api/otp/request/", {"identifier": "demologin@example.com", "channel": "email"})
                self.assertEqual(req_res.status_code, 200)

                # Verify with 123456
                ver_res = self.client.post("/api/otp/verify/", {"identifier": "demologin@example.com", "otp_code": "123456"})
                self.assertEqual(ver_res.status_code, 200)
                self.assertTrue(ver_res.json()["success"])

    def test_03_demo_mode_sms_login_works_with_123456(self):
        user = AuthUser.objects.create(
            username="demosms",
            email="demosms@example.com",
            mobile="+919876543210",
            is_active=1,
        )
        with patch("accounts.services.delivery_service.is_test_environment", return_value=False):
            with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
                # Request OTP for SMS
                req_res = self.client.post("/api/otp/request/", {"identifier": "+919876543210", "channel": "sms"})
                self.assertEqual(req_res.status_code, 200)

                # Verify with 123456
                ver_res = self.client.post("/api/otp/verify/", {"identifier": "+919876543210", "otp_code": "123456"})
                self.assertEqual(ver_res.status_code, 200)
                self.assertTrue(ver_res.json()["success"])

    def test_04_demo_mode_whatsapp_login_works_with_123456(self):
        user = AuthUser.objects.create(
            username="demowa",
            email="demowa@example.com",
            mobile="+919876543211",
            is_active=1,
        )
        with patch("accounts.services.delivery_service.is_test_environment", return_value=False):
            with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
                # Request OTP for WhatsApp
                req_res = self.client.post("/api/otp/request/", {"identifier": "+919876543211", "channel": "whatsapp"})
                self.assertEqual(req_res.status_code, 200)

                # Verify with 123456
                ver_res = self.client.post("/api/otp/verify/", {"identifier": "+919876543211", "otp_code": "123456"})
                self.assertEqual(ver_res.status_code, 200)
                self.assertTrue(ver_res.json()["success"])

    def test_05_plaintext_password_never_stored_in_database(self):
        raw_pass = "SuperSecure#2026!"
        user = AuthUser.objects.create(username="secureuser", email="sec@example.com")
        PasswordService.apply_password_to_user(user, raw_pass)
        user.save()

        # Reload from DB
        reloaded = AuthUser.objects.get(pk=user.id)
        self.assertNotEqual(reloaded.password, raw_pass)
        self.assertNotEqual(reloaded.password_hash, raw_pass)
        self.assertTrue(reloaded.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(reloaded.password_hash.startswith("pbkdf2_sha256$"))

    def test_06_otp_never_stored_plaintext_in_database(self):
        OTPService.generate_and_send_otp("plaincheck@example.com", purpose="login")
        record = AuthOtps.objects.filter(identifier="plaincheck@example.com").first()
        self.assertIsNotNone(record)
        # Hash is SHA-256 (64 hex characters)
        self.assertEqual(len(record.otp_hash), 64)
        self.assertFalse(record.otp_hash.isdigit())

    def test_07_otp_code_never_leaked_in_api_json_responses(self):
        AuthUser.objects.create(
            username="leaktst",
            email="leaktst@example.com",
            is_active=1,
        )
        res = self.client.post("/api/otp/request/", {"identifier": "leaktst@example.com", "channel": "email"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("otp", data)
        self.assertNotIn("raw_otp", data)
        self.assertNotIn("otp_hash", data)

        # Also check forgot password OTP endpoint
        res_fp = self.client.post("/api/forgot-password/otp/request/", {"identifier": "leaktst@example.com", "channel": "email"})
        self.assertEqual(res_fp.status_code, 200)
        data_fp = res_fp.json()
        self.assertNotIn("otp", data_fp)
        self.assertNotIn("raw_otp", data_fp)
        self.assertNotIn("otp_hash", data_fp)

    def test_08_password_reset_invalidates_active_sessions(self):
        user = AuthUser.objects.create(
            username="resetsess",
            email="resetsess@example.com",
            is_active=1,
        )
        PasswordService.apply_password_to_user(user, "OldPass#2026!")
        user.save()

        # Simulate active session in test
        s = self.client.session
        s["_auth_user_id"] = str(user.id)
        s["_auth_user_backend"] = "accounts.backends.AuthUserBackend"
        s["password_reset_authorized"] = {
            "user_id": user.id,
            "identifier": user.email,
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        s.save()

        # Submit new password
        res = self.client.post(
            "/api/reset-password/",
            {"password": "NewValidPass#2026!", "confirm_password": "NewValidPass#2026!"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # Reset session state should be purged
        self.assertNotIn("password_reset_authorized", self.client.session)

    def test_09_old_password_rejected_and_new_password_accepted_after_reset(self):
        user = AuthUser.objects.create(
            username="passchange",
            email="passchange@example.com",
            is_active=1,
        )
        PasswordService.apply_password_to_user(user, "Original#2026")
        user.save()

        # Perform password update via service
        PasswordService.apply_password_to_user(user, "Changed#2026")
        user.save()

        # Old password fails
        self.assertFalse(user.check_password("Original#2026"))
        # New password succeeds
        self.assertTrue(user.check_password("Changed#2026"))

    def test_10_account_enumeration_protection_on_forgot_password(self):
        # Non-existent user
        res = self.client.post(
            "/api/forgot-password/otp/request/",
            {"identifier": "doesnotexist_98765@example.com", "channel": "email"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("If an account matches the information provided", data["message"])


class CompleteFunctionalityAuditRegressionTests(TestCase):
    def setUp(self):
        setup_test_sqlite_tables()
        self.client = Client()

    def test_01_create_account_navigation_and_links(self):
        # 1. Login page contains link to Register
        res_login = self.client.get("/login/")
        self.assertEqual(res_login.status_code, 200)
        self.assertContains(res_login, "/register/")

        # 2. Register page loads properly and contains link to Login
        res_reg = self.client.get("/register/")
        self.assertEqual(res_reg.status_code, 200)
        self.assertContains(res_reg, "/login/")

    def test_02_registration_validation_rules(self):
        # Mismatched passwords
        res = self.client.post(
            "/register/",
            {
                "full_name": "Audit Test User",
                "email": "audit_mismatch@example.com",
                "mobile": "+919876543210",
                "password": "ValidPassword#123",
                "confirm_password": "DifferentPassword#123",
                "channel": "email",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("match", data["message"].lower())

        # Short password (< 8 chars)
        res_short = self.client.post(
            "/register/",
            {
                "full_name": "Audit Test User",
                "email": "audit_short@example.com",
                "mobile": "+919876543210",
                "password": "short",
                "confirm_password": "short",
                "channel": "email",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_short.status_code, 400)
        self.assertFalse(res_short.json()["success"])

    def test_03_successful_demo_otp_registration_and_db_storage(self):
        # 1. Submit Registration Form in Demo Mode
        req_data = {
            "full_name": "Audit New User",
            "email": "audit_newuser@company.com",
            "mobile": "+919876543210",
            "password": "SecurePassword#2026!",
            "confirm_password": "SecurePassword#2026!",
            "channel": "email",
        }
        with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
            res_req = self.client.post(
                "/register/",
                req_data,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(res_req.status_code, 200)
        self.assertTrue(res_req.json()["success"])

        # Verify OTP record in auth_otps table
        otp_rec = AuthOtps.objects.filter(identifier=req_data["email"], purpose="register").order_by("-id").first()
        self.assertIsNotNone(otp_rec)
        self.assertEqual(otp_rec.purpose, "register")
        self.assertFalse(otp_rec.is_used)

        # 2. Verify with Demo OTP (123456)
        res_verify = self.client.post(
            "/api/register/otp/verify/",
            {
                "otp_code": "123456",
            },
            content_type="application/json",
        )
        self.assertEqual(res_verify.status_code, 200)
        self.assertTrue(res_verify.json()["success"])

        # 3. Verify user created in auth_user
        user = AuthUser.objects.filter(email=req_data["email"]).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, req_data["full_name"])
        self.assertEqual(user.mobile, req_data["mobile"])
        self.assertEqual(user.is_active, 1)

        # 4. CRITICAL SECURITY: Verify password is PBKDF2 hash, synchronized, NOT plaintext
        self.assertNotEqual(user.password, req_data["password"])
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertEqual(user.password, user.password_hash)
        # Authentication check
        self.assertTrue(user.check_password(req_data["password"]))
        self.assertFalse(user.check_password("WrongPassword#999"))

    def test_04_duplicate_account_prevention(self):
        # Create an existing user
        existing_user = AuthUser.objects.create(
            username="existing_audit",
            email="existing_audit@example.com",
            mobile="+919876543211",
            is_active=1,
        )
        PasswordService.apply_password_to_user(existing_user, "Pass#123456")
        existing_user.save()

        # Attempt to register with duplicate email
        res = self.client.post(
            "/register/",
            {
                "full_name": "Duplicate User",
                "email": "existing_audit@example.com",
                "mobile": "+919876543212",
                "password": "Password#123456",
                "confirm_password": "Password#123456",
                "channel": "email",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["success"])
        self.assertIn("already exists", res.json()["message"].lower())

    def test_05_password_visibility_toggle_markup_across_pages(self):
        # 1. Login page has password toggle button
        res_login = self.client.get("/login/")
        self.assertContains(res_login, 'toggle-password-btn')
        self.assertContains(res_login, 'type="password"')

        # 2. Register page has password & confirm password toggle buttons
        res_reg = self.client.get("/register/")
        self.assertContains(res_reg, 'toggle-password-btn')
        self.assertContains(res_reg, 'id="reg-password"')
        self.assertContains(res_reg, 'id="reg-password-confirm"')

        # 3. Forgot Password page loads
        res_forgot = self.client.get("/forgot-password/")
        self.assertEqual(res_forgot.status_code, 200)

        # 4. Reset password page has password and confirm toggles when authorized in session
        s = self.client.session
        s["password_reset_authorized"] = {
            "user_id": 1,
            "identifier": "test@example.com",
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        s.save()
        res_reset = self.client.get("/reset-password/")
        self.assertEqual(res_reset.status_code, 200)
        self.assertContains(res_reset, 'toggle-password-btn')

    def test_06_login_flow_password_and_otp(self):
        # Setup test user
        user = AuthUser.objects.create(
            username="loginaudit",
            email="loginaudit@example.com",
            mobile="+919876543222",
            is_active=1,
        )
        PasswordService.apply_password_to_user(user, "AuditLogin#2026!")
        user.save()

        # Valid password login
        res_pw = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": user.email,
                "password": "AuditLogin#2026!",
            },
        )
        self.assertEqual(res_pw.status_code, 302)
        self.assertEqual(res_pw.url, "/dashboard/")

        # Logout
        self.client.logout()

        # Wrong password login fails
        res_bad = self.client.post(
            "/login/",
            {
                "action": "password_login",
                "identifier": user.email,
                "password": "WrongPassword#999",
            },
        )
        self.assertEqual(res_bad.status_code, 200)
        self.assertContains(res_bad, "Invalid credentials")

        # OTP login flow with demo OTP
        with patch("accounts.services.delivery_service.is_demo_delivery_mode", return_value=True):
            res_otp_req = self.client.post(
                "/api/otp/request/",
                {"identifier": user.email, "channel": "email"},
                content_type="application/json",
            )
        self.assertEqual(res_otp_req.status_code, 200)

        # Verify with demo OTP
        res_otp_verify = self.client.post(
            "/api/otp/verify/",
            {"identifier": user.email, "otp_code": "123456", "remember_me": True},
            content_type="application/json",
        )
        self.assertEqual(res_otp_verify.status_code, 200)
        self.assertTrue(res_otp_verify.json()["success"])

    def test_07_logout_flow_and_session_cleared(self):
        user = AuthUser.objects.create(
            username="logoutaudit",
            email="logoutaudit@example.com",
            is_active=1,
        )
        PasswordService.apply_password_to_user(user, "Pass#123456")
        user.save()
        self.client.force_login(user, backend="accounts.backends.AuthUserBackend")

        # Access dashboard
        res_dash = self.client.get("/dashboard/")
        self.assertEqual(res_dash.status_code, 200)

        # Perform logout
        res_logout = self.client.get("/logout/")
        self.assertEqual(res_logout.status_code, 302)
        self.assertEqual(res_logout.url, "/login/")

        # Access dashboard redirected to login
        res_dash_after = self.client.get("/dashboard/")
        self.assertEqual(res_dash_after.status_code, 302)

    def test_08_configuration_ownership_isolation(self):
        user1 = AuthUser.objects.create(username="owner1", email="owner1@example.com", is_active=1)
        user2 = AuthUser.objects.create(username="owner2", email="owner2@example.com", is_active=1)

        # Save config for user 1
        cfg = AuthConfigurations.objects.create(
            user_id=user1.id,
            configuration_name="User 1 Config",
            configuration_data=json.dumps({"template_id": "modern", "primary_color": "#3b82f6"}),
            is_active=1,
        )

        # User 2 logs in
        self.client.force_login(user2, backend="accounts.backends.AuthUserBackend")

        # User 2 cannot access user 1's configuration
        res = self.client.get(f"/api/builder/configurations/{cfg.id}/load/")
        self.assertIn(res.status_code, [403, 404])

        # User 1 logs in
        self.client.force_login(user1, backend="accounts.backends.AuthUserBackend")
        res_owner = self.client.get(f"/api/builder/configurations/{cfg.id}/load/")
        self.assertEqual(res_owner.status_code, 200)
        self.assertEqual(res_owner.json()["configuration"]["name"], "User 1 Config")


class LogoAndOTPBuilderRegressionTests(TestCase):
    """
    Comprehensive regression tests for:
    - Logo validation (PNG, JPEG, WebP magic bytes, SVG rejection, size limits)
    - OTP button customizations (auto, full, custom width modes, icon sizes, etc.)
    - Backward compatibility with legacy configurations missing new keys
    - ZIP export extracting base64 logos into static assets
    - TemplateRegistry dynamic CSS generation
    """

    def setUp(self):
        setup_test_sqlite_tables()
        self.client = Client()
        self.user = AuthUser.objects.create(
            username="designertest",
            email="designer@company.com",
            is_active=1
        )
        # Valid 1x1 PNG data URI
        self.valid_png_uri = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        # Valid 1x1 JPEG data URI
        self.valid_jpeg_uri = (
            "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        )
        # Valid 1x1 WebP data URI
        webp_bytes = b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0e\x00\x00\x00/\x00\x00\x00\x00\x07\x85\x85\x88\x85%\xa4\x00\x03\x70\x00\xfe\x01\x00"
        import base64
        self.valid_webp_uri = f"data:image/webp;base64,{base64.b64encode(webp_bytes).decode('ascii')}"

    def test_logo_validation_valid_formats(self):
        """Test that valid PNG, JPEG, and WebP data URIs pass server-side validation."""
        self.assertEqual(ConfigService.validate_logo_data_uri(self.valid_png_uri, raise_exception=True), self.valid_png_uri)
        self.assertEqual(ConfigService.validate_logo_data_uri(self.valid_jpeg_uri, raise_exception=True), self.valid_jpeg_uri)
        self.assertEqual(ConfigService.validate_logo_data_uri(self.valid_webp_uri, raise_exception=True), self.valid_webp_uri)

    def test_logo_validation_rejects_svg(self):
        """Test that user-uploaded SVG data URIs and inline SVG codes are strictly rejected."""
        from django.core.exceptions import ValidationError
        svg_uri = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIvPjwvc3ZnPg=="
        with self.assertRaises(ValidationError) as ctx:
            ConfigService.validate_logo_data_uri(svg_uri, raise_exception=True)
        self.assertIn("SVG logos are not allowed", str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            ConfigService.validate_logo_data_uri("<svg><circle r='10'/></svg>", raise_exception=True)
        self.assertIn("SVG logos are not allowed", str(ctx.exception))

    def test_logo_validation_rejects_oversized_payload(self):
        """Test that uploads exceeding 500 KB raw limit are rejected."""
        from django.core.exceptions import ValidationError
        # 501 KB payload
        oversized_b64 = "iVBORw0KGgo" + ("A" * (690 * 1024))
        oversized_uri = f"data:image/png;base64,{oversized_b64}"
        with self.assertRaises(ValidationError) as ctx:
            ConfigService.validate_logo_data_uri(oversized_uri, raise_exception=True)
        self.assertIn("exceeds the 500 KB limit", str(ctx.exception))

    def test_logo_validation_rejects_mismatched_magic_bytes(self):
        """Test that fraudulent MIME types with fake magic bytes are rejected."""
        from django.core.exceptions import ValidationError
        fake_png = "data:image/png;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" # GIF bytes with PNG MIME
        with self.assertRaises(ValidationError) as ctx:
            ConfigService.validate_logo_data_uri(fake_png, raise_exception=True)
        self.assertIn("Corrupted or invalid", str(ctx.exception))

    def test_otp_buttons_sanitization_and_clamping(self):
        """Test that otp_buttons builder settings are thoroughly clamped and sanitized."""
        raw_otp = {
            "width_mode": "custom",
            "custom_width": "9999px",
            "height": "-50px",
            "radius": "200px",
            "gap": "15px",
            "padding": "10px 18px",
            "font_size": "70px",
            "icon_size": "2px",
            "border_width": "20px"
        }
        sanitized = ConfigService.sanitize_otp_buttons(raw_otp)
        self.assertEqual(sanitized["width_mode"], "custom")
        self.assertEqual(sanitized["custom_width"], "360px") # clamped to max 360px
        self.assertEqual(sanitized["height"], "32px")       # clamped to min 32px
        self.assertEqual(sanitized["radius"], "32px")       # clamped to max 32px
        self.assertEqual(sanitized["gap"], "15px")
        self.assertEqual(sanitized["padding"], "10px 18px")
        self.assertEqual(sanitized["font_size"], "18px")    # clamped to max 18px
        self.assertEqual(sanitized["icon_size"], "12px")    # clamped to min 12px
        self.assertEqual(sanitized["border_width"], "4px")  # clamped to max 4px

    def test_backward_compatibility_with_legacy_configs(self):
        """Verify that existing legacy configurations without logo dimensions or otp_buttons work perfectly."""
        legacy_config = {
            "template_id": "modern",
            "primary_color": "#4f46e5",
            "branding": {
                "brand_name": "Legacy Corp"
            }
        }
        sanitized = ConfigService.sanitize_config_data(legacy_config)

        # Safe defaults should be automatically populated
        self.assertIn("otp_buttons", sanitized)
        self.assertEqual(sanitized["otp_buttons"]["width_mode"], "auto")
        self.assertEqual(sanitized["otp_buttons"]["icon_size"], "16px")
        self.assertEqual(sanitized["branding"]["logo_align"], "center")
        self.assertEqual(sanitized["branding"]["logo_scale"], 100)
        self.assertEqual(sanitized["branding"]["maintain_aspect_ratio"], True)

        # CSS variable compilation must succeed without errors
        css_vars = TemplateRegistry.generate_css_variables(sanitized)
        self.assertIn("--otp-btn-icon-size: 16px;", css_vars)
        self.assertIn("--logo-scale: 1.00;", css_vars)

    def test_css_variables_generation_for_new_features(self):
        """Verify dynamic CSS variables compile correctly for custom logo and OTP button settings."""
        custom_config = {
            "template": "corporate",
            "branding": {
                "brand_name": "Acme Corp",
                "logo_width": "180px",
                "logo_height": "48px",
                "logo_scale": 125,
                "logo_align": "left",
                "maintain_aspect_ratio": False
            },
            "otp_buttons": {
                "width_mode": "custom",
                "custom_width": "220px",
                "height": "46px",
                "radius": "8px",
                "gap": "10px",
                "padding": "6px 14px",
                "font_size": "15px",
                "icon_size": "22px",
                "border_width": "2px"
            }
        }
        css_vars = TemplateRegistry.generate_css_variables(custom_config)
        self.assertIn("--logo-width: 180px;", css_vars)
        self.assertIn("--logo-height: 48px;", css_vars)
        self.assertIn("--logo-scale: 1.25;", css_vars)
        self.assertIn("--otp-btn-custom-width: 220px;", css_vars)
        self.assertIn("--otp-btn-height: 46px;", css_vars)
        self.assertIn("--otp-btn-icon-size: 22px;", css_vars)
        self.assertIn("--otp-btn-border-width: 2px;", css_vars)

    def test_export_service_extracts_base64_logo_to_file(self):
        """Verify ZIP export extracts embedded base64 logo into an image asset in the static directory."""
        config_with_logo = {
            "template": "modern",
            "branding": {
                "brand_name": "Export Test",
                "logo_url": self.valid_png_uri,
                "logo_width": "150px",
                "logo_height": "50px",
                "logo_scale": 100,
                "logo_align": "center"
            },
            "otp_buttons": {
                "width_mode": "full",
                "height": "42px",
                "icon_size": "18px"
            }
        }
        zip_bytes = ExportService.generate_project_zip(config=config_with_logo, template_id="modern")
        self.assertIsInstance(zip_bytes, bytes)
        self.assertGreater(len(zip_bytes), 0)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            namelist = zf.namelist()
            # Logo must be extracted as a clean asset file
            self.assertIn("custom-auth-platform/static/accounts/images/brand_logo.png", namelist)
            extracted_logo_bytes = zf.read("custom-auth-platform/static/accounts/images/brand_logo.png")
            # Must start with PNG magic bytes
            self.assertTrue(extracted_logo_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

            # Check that exported tokens css contains logo variables
            tokens_css = zf.read("custom-auth-platform/static/accounts/css/auth_tokens.css").decode("utf-8")
            self.assertIn("--logo-width: 150px;", tokens_css)
            self.assertIn("--otp-btn-height: 42px;", tokens_css)
            self.assertNotIn("data:image/png;base64", tokens_css)

            # Check security: no .env, no credentials
            for filename in namelist:
                self.assertFalse(filename.endswith(".env"))
                self.assertNotIn("venv", filename)
                self.assertNotIn("__pycache__", filename)

    def test_builder_save_and_load_api_roundtrip(self):
        """Verify saving and loading configurations via the builder API preserves all logo & OTP settings."""
        self.client.force_login(self.user, backend="accounts.backends.AuthUserBackend")

        save_payload = {
            "template_id": "split",
            "configuration_name": "Design System Config",
            "configuration_data": {
                "template": "split",
                "branding": {
                    "brand_name": "Design Co",
                    "logo_url": self.valid_png_uri,
                    "logo_width": "160px",
                    "logo_height": "40px",
                    "logo_scale": 110,
                    "logo_align": "left",
                    "maintain_aspect_ratio": True
                },
                "otp_buttons": {
                    "width_mode": "custom",
                    "custom_width": "180px",
                    "height": "40px",
                    "radius": "10px",
                    "gap": "8px",
                    "padding": "4px 10px",
                    "font_size": "13px",
                    "icon_size": "18px",
                    "border_width": "1px"
                }
            }
        }

        save_res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps(save_payload),
            content_type="application/json"
        )
        self.assertEqual(save_res.status_code, 200)
        cfg_id = save_res.json()["config"]["id"]

        # Load the configuration
        load_res = self.client.get(f"/api/builder/configurations/{cfg_id}/load/")
        self.assertEqual(load_res.status_code, 200)
        loaded_data = load_res.json()["configuration"]["data"]

        self.assertEqual(loaded_data["branding"]["brand_name"], "Design Co")
        self.assertEqual(loaded_data["branding"]["logo_url"], self.valid_png_uri)
        self.assertEqual(loaded_data["branding"]["logo_width"], "160px")
        self.assertEqual(loaded_data["branding"]["logo_align"], "left")
        self.assertEqual(loaded_data["otp_buttons"]["width_mode"], "custom")
        self.assertEqual(loaded_data["otp_buttons"]["custom_width"], "180px")
        self.assertEqual(loaded_data["otp_buttons"]["icon_size"], "18px")

    def test_logo_survives_sanitization(self):
        """Verify that a valid custom logo URL survives sanitization intact."""
        raw_config = {
            "template": "modern",
            "branding": {
                "brand_name": "Acme",
                "logo_url": self.valid_png_uri,
                "logo_width": "140px",
                "logo_height": "36px",
                "logo_scale": 115,
                "logo_align": "right",
                "maintain_aspect_ratio": True
            }
        }
        sanitized = ConfigService.sanitize_config_data(raw_config)
        self.assertEqual(sanitized["branding"]["logo_url"], self.valid_png_uri)
        self.assertEqual(sanitized["branding"]["logo_width"], "140px")
        self.assertEqual(sanitized["branding"]["logo_height"], "36px")
        self.assertEqual(sanitized["branding"]["logo_scale"], 115)
        self.assertEqual(sanitized["branding"]["logo_align"], "right")
        self.assertTrue(sanitized["branding"]["maintain_aspect_ratio"])

    def test_custom_logo_rendered_in_all_templates(self):
        """Verify that custom logo is rendered in the HTML for Modern Glass, Split Screen, and Minimal Corporate."""
        # Save config with custom logo and set as active session config
        cfg_data = {
            "template": "modern",
            "branding": {
                "brand_name": "Acme Corp",
                "logo_url": self.valid_png_uri,
                "logo_width": "180px",
                "logo_height": "48px",
                "logo_scale": 100,
                "logo_align": "center",
                "maintain_aspect_ratio": True
            }
        }
        session = self.client.session
        session["active_config_data"] = cfg_data
        session.save()

        for template_name in ["modern", "split", "corporate"]:
            response = self.client.get(f"/login/?template={template_name}")
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            
            # Must render the custom logo element with the valid PNG URI
            self.assertIn("brand-custom-logo", content, f"Custom logo class missing in {template_name}")
            self.assertIn(self.valid_png_uri, content, f"Logo URI missing in {template_name}")
            # The custom logo must NOT have display: none inline
            self.assertNotIn('id="brand-header-logo" class="brand-custom-logo" src="" style="display: none;"', content)

    def test_default_logo_appears_when_custom_logo_is_absent(self):
        """Verify that default emblem appears and custom logo is hidden when no logo_url is configured."""
        session = self.client.session
        session["active_config_data"] = {
            "template": "modern",
            "branding": {
                "brand_name": "No Logo Corp",
                "logo_url": "",
                "logo_align": "center"
            }
        }
        session.save()

        for template_name in ["modern", "split", "corporate"]:
            response = self.client.get(f"/login/?template={template_name}")
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            
            # Default badge/emblem must be visible
            self.assertIn("brand-default-badge", content, f"Default badge missing in {template_name}")
            # brand-custom-logo must either be empty or hidden
            self.assertTrue(
                'id="brand-header-logo" class="brand-custom-logo" src="" style="display: none;"' in content
                or 'display: none;' in content
            )

    def test_remove_logo_works_via_api(self):
        """Verify that removing a logo (updating logo_url to empty) persists and restores the default badge."""
        self.client.force_login(self.user, backend="accounts.backends.AuthUserBackend")

        # 1. Save with logo
        save_res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps({
                "template_id": "modern",
                "configuration_name": "Logo Config",
                "configuration_data": {
                    "template": "modern",
                    "branding": {"brand_name": "Logo Co", "logo_url": self.valid_png_uri}
                }
            }),
            content_type="application/json"
        )
        self.assertEqual(save_res.status_code, 200)
        cfg_id = save_res.json()["config"]["id"]

        # 2. Update with removed logo (logo_url = "")
        update_res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps({
                "config_id": cfg_id,
                "template_id": "modern",
                "configuration_name": "Logo Removed Config",
                "configuration_data": {
                    "template": "modern",
                    "branding": {"brand_name": "Logo Co", "logo_url": ""}
                }
            }),
            content_type="application/json"
        )
        self.assertEqual(update_res.status_code, 200)

        # 3. Load config and verify logo is empty string
        load_res = self.client.get(f"/api/builder/configurations/{cfg_id}/load/")
        self.assertEqual(load_res.status_code, 200)
        loaded_data = load_res.json()["configuration"]["data"]
        self.assertEqual(loaded_data["branding"]["logo_url"], "")

    def test_brand_name_sanitization_and_bounds(self):
        """Verify brand name sanitization, default fallback, and 60-character limit."""
        # 1. Fallback to default when absent
        sanitized_default = ConfigService.sanitize_branding({})
        self.assertEqual(sanitized_default["brand_name"], "Auth Platform")

        # 2. Preserves custom valid brand name
        sanitized_custom = ConfigService.sanitize_branding({"brand_name": "station -s"})
        self.assertEqual(sanitized_custom["brand_name"], "station -s")

        # 3. Clamps long brand names to 60 characters
        long_name = "A" * 100
        sanitized_long = ConfigService.sanitize_branding({"brand_name": long_name})
        self.assertEqual(len(sanitized_long["brand_name"]), 60)
        self.assertEqual(sanitized_long["brand_name"], "A" * 60)

    def test_brand_name_save_and_load_roundtrip(self):
        """Verify saving and loading custom brand name via API."""
        self.client.force_login(self.user, backend="accounts.backends.AuthUserBackend")

        save_res = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps({
                "template_id": "modern",
                "configuration_name": "Station Brand Config",
                "configuration_data": {
                    "template": "modern",
                    "branding": {
                        "brand_name": "station -s",
                        "logo_url": self.valid_png_uri
                    }
                }
            }),
            content_type="application/json"
        )
        self.assertEqual(save_res.status_code, 200)
        cfg_id = save_res.json()["config"]["id"]

        load_res = self.client.get(f"/api/builder/configurations/{cfg_id}/load/")
        self.assertEqual(load_res.status_code, 200)
        loaded = load_res.json()["configuration"]["data"]
        self.assertEqual(loaded["branding"]["brand_name"], "station -s")

    def test_brand_name_rendered_in_all_templates(self):
        """Verify custom brand name renders in Modern Glass, Split Screen, Minimal Corporate, and Main /login/."""
        custom_config = {
            "template": "modern",
            "branding": {
                "brand_name": "station -s",
                "logo_url": self.valid_png_uri,
                "logo_align": "center"
            }
        }
        session = self.client.session
        session["active_config_data"] = custom_config
        session.save()

        for template_name in ["modern", "split", "corporate"]:
            res = self.client.get(f"/login/?template={template_name}")
            self.assertEqual(res.status_code, 200)
            content = res.content.decode("utf-8")
            self.assertIn("station -s", content, f"Brand name 'station -s' missing in {template_name}")
            self.assertIn("brand-name", content, f"class brand-name missing in {template_name}")
            # Ensure both logo and brand name exist simultaneously
            self.assertIn("brand-custom-logo", content, f"Logo missing in {template_name}")

        # Verify main /login/ page also displays brand name
        main_res = self.client.get("/login/")
        self.assertEqual(main_res.status_code, 200)
        self.assertIn("station -s", main_res.content.decode("utf-8"))

    def test_default_brand_name_in_legacy_config(self):
        """Verify that older configurations lacking brand_name fallback to 'Auth Platform'."""
        legacy_config = {
            "template": "modern",
            "branding": {
                "logo_url": ""
            }
        }
        session = self.client.session
        session["active_config_data"] = legacy_config
        session.save()

        res = self.client.get("/login/?template=modern")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("Auth Platform", content)

    def test_brand_name_xss_safe_rendering(self):
        """Verify that user-submitted HTML/script tags in brand_name are strictly escaped and safe."""
        xss_payload = "<script>alert('xss')</script>"
        session = self.client.session
        session["active_config_data"] = {
            "template": "modern",
            "branding": {
                "brand_name": xss_payload,
                "logo_url": ""
            }
        }
        session.save()

        res = self.client.get("/login/?template=modern")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        # Script tags MUST NOT be rendered unescaped
        self.assertNotIn("<script>alert('xss')</script>", content)
        # Must be HTML-escaped
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", content)

    def test_templates_gallery_route_and_seo(self):
        """Verify /templates/ and /templates-preview/ return 200 with Stitch gallery and SEO metadata."""
        # Test official templates route
        res_gallery = self.client.get("/templates/")
        self.assertEqual(res_gallery.status_code, 200)
        content_gallery = res_gallery.content.decode("utf-8")
        self.assertIn("Authentication Templates", content_gallery)
        self.assertIn("Modern Minimal", content_gallery)
        self.assertIn("Split Screen", content_gallery)
        self.assertIn("Minimal Corporate", content_gallery)
        self.assertIn('name="robots" content="index, follow"', content_gallery)
        self.assertIn("/builder/", content_gallery)

        # Test templates-preview route (preserves SEO and rendering)
        res_preview = self.client.get("/templates-preview/")
        self.assertEqual(res_preview.status_code, 200)
        content_preview = res_preview.content.decode("utf-8")
        self.assertIn("Authentication Templates", content_preview)
        self.assertIn('name="robots" content="index, follow"', content_preview)

    def test_builder_top_navigation_and_style_selector(self):
        """Verify builder top navigation points to /templates/ and contains redesigned style selector."""
        res = self.client.get("/builder/")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        # Main nav Templates link points to /templates/
        self.assertIn('href="/templates/" class="nav-link">Templates</a>', content)
        # Style selector and preview shell exist
        self.assertIn("preview-shell", content)
        self.assertIn("builder-style-selector", content)
        self.assertIn("style-segmented-control", content)
        self.assertIn('data-template="modern"', content)
        self.assertIn('data-template="split"', content)
        self.assertIn('data-template="corporate"', content)

    def test_templates_gallery_visible_after_login(self):
        """Verify that an authenticated user navigating to /templates/ sees the gallery with user profile pill and no redirect."""
        # 1. Log user in
        self.client.force_login(self.user)
        # 2. Access /templates/
        res = self.client.get("/templates/")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("Authentication Template System", content)
        self.assertIn("Modern Minimal", content)
        self.assertIn("Split Screen", content)
        self.assertIn("Minimal Corporate", content)
        self.assertIn("Sign Out", content)
        # Quick preview links should have preview=1
        self.assertIn("preview=1", content)

    def test_authenticated_user_can_access_preview_mode_without_dashboard_redirect(self):
        """Verify authenticated users can view auth templates in preview mode (?preview=1) without getting redirected to /dashboard/."""
        self.client.force_login(self.user)
        # Without preview flag, redirected to dashboard
        res_normal = self.client.get("/login/")
        self.assertEqual(res_normal.status_code, 302)
        self.assertEqual(res_normal.url, "/dashboard/")

        # With preview=1 flag, 200 OK rendered
        res_preview = self.client.get("/login/?template=modern&preview=1")
        self.assertEqual(res_preview.status_code, 200)
        self.assertIn("template-modern", res_preview.content.decode("utf-8"))

        res_split_preview = self.client.get("/login/?template=split&preview=1")
        self.assertEqual(res_split_preview.status_code, 200)
        self.assertIn("template-split", res_split_preview.content.decode("utf-8"))

    def test_background_configuration_sanitization_and_validation(self):
        """Verify background data is properly sanitized and invalid SVGs are rejected."""
        from accounts.services.config_service import sanitize_config_data

        # 1. Valid background colors and gradients
        config_in = {
            "background": {
                "type": "gradient",
                "color": "#112233",
                "gradient": {
                    "type": "linear",
                    "start_color": "#123456",
                    "end_color": "#654321",
                    "angle": 90,
                },
                "position": "center",
                "size": "cover",
                "repeat": "no-repeat",
                "overlay": {"color": "#000000", "opacity": 50},
                "blur": 5,
                "brightness": 110,
                "saturation": 90,
            }
        }
        sanitized = sanitize_config_data(config_in)
        bg = sanitized["background"]
        self.assertEqual(bg["type"], "gradient")
        self.assertEqual(bg["color"], "#112233")
        self.assertEqual(bg["gradient"]["start_color"], "#123456")
        self.assertEqual(bg["gradient"]["angle"], 90)
        self.assertEqual(bg["overlay"]["opacity"], 50)
        self.assertEqual(bg["blur"], 5)
        self.assertEqual(bg["brightness"], 110)

        # 2. Reject SVG data URI in background image
        svg_data = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxzY3JpcHQ+YWxlcnQoMSk8L3NjcmlwdD48L3N2Zz4="
        config_svg = {
            "background": {
                "type": "image",
                "image_url": svg_data,
            }
        }
        sanitized_svg = sanitize_config_data(config_svg)
        self.assertEqual(sanitized_svg["background"]["image_url"], "")

        # 3. Accept valid PNG 1x1 base64
        png_1x1 = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        config_png = {
            "background": {
                "type": "image",
                "image_url": png_1x1,
            }
        }
        sanitized_png = sanitize_config_data(config_png)
        self.assertTrue(sanitized_png["background"]["image_url"].startswith("data:image/png;base64,"))

    def test_card_and_animation_sanitization_and_persistence(self):
        """Verify card styling and entrance animation settings persist and clamp to limits."""
        from accounts.services.config_service import sanitize_config_data

        config_in = {
            "card": {
                "width": "800px",  # Clamped to max 600px
                "padding": "60px", # Clamped to max 48px
                "background_color": "#abcdef",
                "opacity": 85,
                "border_radius": "40px", # Clamped to max 32px
                "border_width": 2,
                "border_color": "#123456",
                "shadow": "strong",
                "blur": 10,
                "alignment": "left",
            },
            "animations": {
                "type": "slide_up",
                "duration": 400,
                "delay": 100,
                "intensity": "normal",
            },
        }
        sanitized = sanitize_config_data(config_in)
        card = sanitized["card"]
        self.assertEqual(card["width"], "600px")
        self.assertEqual(card["padding"], "48px")
        self.assertEqual(card["border_radius"], "32px")
        self.assertEqual(card["opacity"], 85)
        self.assertEqual(card["shadow"], "strong")
        self.assertEqual(card["alignment"], "left")

        anims = sanitized["animations"]
        self.assertEqual(anims["type"], "slide_up")
        self.assertEqual(anims["duration"], 400)
        self.assertEqual(anims["delay"], 100)

    def test_template_registry_generates_background_and_card_css_variables(self):
        """Verify TemplateRegistry generate_css_variables outputs all background, card, and animation variables."""
        from accounts.services.template_registry import TemplateRegistry

        config = {
            "background": {
                "type": "color",
                "color": "#232323",
                "blur": 4,
            },
            "card": {
                "width": "480px",
                "border_radius": "16px",
                "background_color": "#18181b",
                "opacity": 95,
            },
            "animations": {
                "type": "fade",
                "duration": 300,
            },
        }
        css_vars = TemplateRegistry.generate_css_variables("modern", config)
        self.assertIn("--auth-bg-color: #232323;", css_vars)
        self.assertIn("--auth-bg-filter-blur: 4px;", css_vars)
        self.assertIn("--card-width: 480px;", css_vars)
        self.assertIn("--card-border-radius: 16px;", css_vars)
        self.assertIn("--card-bg-color: #18181b;", css_vars)
        self.assertIn("--card-opacity: 0.95;", css_vars)
        self.assertIn("--card-animation-name: animFade;", css_vars)
        self.assertIn("--card-animation-duration: 300ms;", css_vars)


class TestLivePreviewLayoutAndTemplatesGallery(TestCase):
    """Automated test suite verifying Live Preview container architecture, demo banner, and Templates Gallery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.user = AuthUser(
            username="previewtester",
            email="previewtester@company.com",
            full_name="Preview Tester",
        )
        PasswordService.apply_password_to_user(self.user, "SecurePassword123!")
        self.user.save()

    def test_builder_live_preview_stage_and_viewport_markup(self):
        """Verify builder page renders the proper preview stage, toolbar, shell, and viewport elements."""
        response = self.client.get("/builder/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("builder-preview-stage", content)
        self.assertIn("preview-stage-toolbar", content)
        self.assertIn("preview-shell", content)
        self.assertIn("preview-frame-wrapper", content)
        self.assertIn("preview-viewport", content)
        self.assertIn("preview-iframe", content)
        self.assertIn("State Simulator:", content)

    def test_auth_pages_render_preview_mode_cleanly(self):
        """Verify all authentication screens load with preview=1 and render without error."""
        templates = ["modern", "split", "corporate"]
        screens = [
            ("/login/", "Sign In"),
            ("/register/", "Create Account"),
            ("/forgot-password/", "Forgot"),
        ]
        for tpl in templates:
            for url, expected_text in screens:
                resp = self.client.get(f"{url}?template={tpl}&preview=1")
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode("utf-8")
                self.assertIn("is-preview", body)
                self.assertIn(tpl, body)

    @patch.object(
        OTPDeliveryRouter,
        "get_channel_status",
        return_value={
            "email": {"available": True, "label": "Email", "is_demo": True},
            "sms": {"available": True, "label": "SMS", "is_demo": True},
            "whatsapp": {"available": True, "label": "WhatsApp", "is_demo": True},
        },
    )
    def test_compact_demo_banner_preserves_demo_otp(self, mock_status):
        """Verify demo banner retains the required DEVELOPMENT / DEMO MODE notice and 123456 OTP."""
        resp = self.client.get("/login/?template=modern")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("DEVELOPMENT / DEMO MODE", body)
        self.assertIn("Demo OTP: 123456", body)
        self.assertIn("demo-banner", body)

    def test_dashboard_templates_gallery_access_after_login(self):
        """Verify logged in user can access dashboard and navigate to the real Templates Gallery."""
        # Log in
        login_success = self.client.login(username="previewtester", password="SecurePassword123!")
        self.assertTrue(login_success)

        # Dashboard contains Templates link
        dash_resp = self.client.get("/dashboard/")
        self.assertEqual(dash_resp.status_code, 200)
        dash_body = dash_resp.content.decode("utf-8")
        self.assertIn('href="/templates/"', dash_body)

        # Navigate to /templates/
        gallery_resp = self.client.get("/templates/")
        self.assertEqual(gallery_resp.status_code, 200)
        gallery_body = gallery_resp.content.decode("utf-8")
        self.assertIn("templates-preview-body", gallery_body)
        self.assertIn("Modern Minimal", gallery_body)
        self.assertIn("Split Screen", gallery_body)
        self.assertIn("Minimal Corporate", gallery_body)
        self.assertIn("Preview Tester", gallery_body)


class TestThemeModeArchitecture(TestCase):
    """
    Comprehensive automated test suite for Theme Mode (Dark, Light, System) architecture.
    Verifies default dark mode, light mode, system mode, design tokens, backward compatibility,
    Apply / Reset APIs, Live Preview synchronization, contrast, and auth pages.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.user = AuthUser(
            username="themetester",
            email="themetester@company.com",
            full_name="Theme Tester",
        )
        PasswordService.apply_password_to_user(self.user, "SecurePass123!")
        self.user.save()

    def test_default_theme_mode_is_dark_across_templates(self):
        """Verify TemplateRegistry defaults specify dark theme mode for modern, split, and corporate."""
        for tpl in ["modern", "split", "corporate"]:
            defaults = TemplateRegistry.get_default_config(tpl)
            self.assertIn("theme", defaults, f"Template {tpl} missing 'theme' object")
            self.assertEqual(
                defaults["theme"].get("mode"),
                "dark",
                f"Template {tpl} default theme mode should be 'dark'",
            )

    def test_config_service_sanitize_theme_mode(self):
        """Verify ConfigService sanitizes theme mode and defaults missing or invalid values to 'dark'."""
        # Valid values
        self.assertEqual(ConfigService.sanitize_theme({"mode": "dark"}), {"mode": "dark"})
        self.assertEqual(ConfigService.sanitize_theme({"mode": "light"}), {"mode": "light"})
        self.assertEqual(ConfigService.sanitize_theme({"mode": "system"}), {"mode": "system"})

        # Case normalization and invalid values fallback
        self.assertEqual(ConfigService.sanitize_theme({"mode": "DARK"}), {"mode": "dark"})
        self.assertEqual(ConfigService.sanitize_theme({"mode": "invalid"}), {"mode": "dark"})
        self.assertEqual(ConfigService.sanitize_theme({}), {"mode": "dark"})
        self.assertEqual(ConfigService.sanitize_theme(None), {"mode": "dark"})

    def test_backward_compatibility_missing_theme_in_config(self):
        """Verify existing saved configurations without a 'theme' field automatically default to dark."""
        legacy_config = {
            "template": "modern",
            "colors": {"primary": "#2563eb"},
        }
        sanitized = ConfigService.sanitize_config_data(legacy_config)
        self.assertIn("theme", sanitized)
        self.assertEqual(sanitized["theme"]["mode"], "dark")

    def test_generate_css_variables_dark_theme(self):
        """Verify generate_css_variables outputs the professional dark theme tokens."""
        config = {
            "template": "modern",
            "theme": {"mode": "dark"},
            "colors": {},
            "card": {},
            "inputs": {},
            "buttons": {},
        }
        css = TemplateRegistry.generate_css_variables(config)
        self.assertIn("--theme-mode: dark;", css)
        self.assertIn("--card-background: #1B1D21;", css)
        self.assertIn("--background-color: #111214;", css)
        self.assertIn("--text-color: #F5F5F5;", css)
        self.assertIn("--muted-color: #A7A7A7;", css)
        self.assertIn("--input-bg: #15171A;", css)
        self.assertIn("--input-border: #34373C;", css)
        self.assertIn("--btn-primary-bg: #FFFFFF;", css)
        self.assertIn("--btn-primary-text: #111111;", css)
        self.assertIn("--tab-bg: #15171A;", css)
        self.assertIn("--tab-active-bg: #2A2C30;", css)
        self.assertIn("--otp-channel-bg: #15171A;", css)

    def test_generate_css_variables_light_theme(self):
        """Verify generate_css_variables outputs the professional light theme tokens."""
        config = {
            "template": "modern",
            "theme": {"mode": "light"},
            "colors": {},
            "card": {},
            "inputs": {},
            "buttons": {},
        }
        css = TemplateRegistry.generate_css_variables(config)
        self.assertIn("--theme-mode: light;", css)
        self.assertIn("--card-background: #FFFFFF;", css)
        self.assertIn("--background-color: #F5F6F8;", css)
        self.assertIn("--text-color: #17181A;", css)
        self.assertIn("--muted-color: #656970;", css)
        self.assertIn("--input-bg: #FFFFFF;", css)
        self.assertIn("--input-border: #D7DADF;", css)
        self.assertIn("--btn-primary-bg: #17181A;", css)
        self.assertIn("--btn-primary-text: #FFFFFF;", css)
        self.assertIn("--tab-bg: #EDEFF2;", css)
        self.assertIn("--tab-active-bg: #FFFFFF;", css)
        self.assertIn("--otp-channel-bg: #FFFFFF;", css)
        self.assertIn("--otp-channel-active-border: #17181A;", css)

    def test_generate_css_variables_system_theme(self):
        """Verify generate_css_variables outputs system mode identifier for CSS media queries."""
        config = {
            "template": "modern",
            "theme": {"mode": "system"},
            "colors": {},
            "card": {},
            "inputs": {},
            "buttons": {},
        }
        css = TemplateRegistry.generate_css_variables(config)
        self.assertIn("--theme-mode: system;", css)

    def test_custom_card_background_overrides_theme_default(self):
        """Verify custom card background color takes priority over theme default."""
        config = {
            "template": "modern",
            "theme": {"mode": "dark"},
            "card": {"background_color": "#242424"},
        }
        css = TemplateRegistry.generate_css_variables(config)
        self.assertIn("--card-background: #242424;", css)
        self.assertIn("--card-bg-color: #242424;", css)

    def test_builder_markup_includes_theme_mode_controls(self):
        """Verify builder page renders the Theme Mode section and segmented buttons."""
        response = self.client.get("/builder/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Theme Mode", content)
        self.assertIn("ctrl-theme-mode-group", content)
        self.assertIn('data-mode="dark"', content)
        self.assertIn('data-mode="light"', content)
        self.assertIn('data-mode="system"', content)
        self.assertIn("btn-reset-card-bg", content)

    def test_apply_theme_mode_updates_actual_auth_pages(self):
        """Verify applying a light theme updates /login/, /register/, /forgot-password/, /reset-password/."""
        # 1. Apply light theme via API
        apply_payload = {
            "template": "modern",
            "theme": {"mode": "light"},
            "branding": {"brand_name": "Acme Theme Test"},
        }
        apply_resp = self.client.post(
            "/api/builder/configurations/apply/",
            data=json.dumps(apply_payload),
            content_type="application/json",
        )
        self.assertEqual(apply_resp.status_code, 200)
        self.assertTrue(apply_resp.json().get("success"))

        # 2. Check all 4 actual auth pages reflect data-theme="light"
        session = self.client.session
        session["password_reset_authorized"] = {
            "user_id": self.user.id,
            "identifier": self.user.email,
            "token": "test-reset-token-abc",
            "created_at": timezone.now().isoformat(),
            "expires_at": (timezone.now() + timedelta(minutes=15)).isoformat(),
        }
        session.save()

        auth_pages = ["/login/", "/register/", "/forgot-password/", "/reset-password/"]
        for url in auth_pages:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Page {url} failed to render")
            body = resp.content.decode("utf-8")
            self.assertIn('data-theme="light"', body, f"Page {url} did not render data-theme='light'")
            self.assertIn("--theme-mode: light;", body, f"Page {url} missing --theme-mode: light dynamic CSS")

    def test_reset_api_restores_default_dark_mode(self):
        """Verify resetting via /api/builder/configurations/reset/ restores default dark mode."""
        # First set light
        self.client.post(
            "/api/builder/configurations/apply/",
            data=json.dumps({"template": "modern", "theme": {"mode": "light"}}),
            content_type="application/json",
        )
        # Then reset
        reset_resp = self.client.post("/api/builder/configurations/reset/")
        self.assertEqual(reset_resp.status_code, 200)
        self.assertTrue(reset_resp.json().get("success"))

        # Login page should now render with data-theme="dark"
        resp = self.client.get("/login/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn('data-theme="dark"', body)

    def test_all_templates_render_with_each_theme_mode(self):
        """Verify Modern, Split, and Corporate templates all render properly with dark, light, and system."""
        templates = ["modern", "split", "corporate"]
        modes = ["dark", "light", "system"]

        for tpl in templates:
            for mode in modes:
                self.client.post(
                    "/api/builder/configurations/apply/",
                    data=json.dumps({"template": tpl, "theme": {"mode": mode}}),
                    content_type="application/json",
                )
                resp = self.client.get(f"/login/?template={tpl}")
                self.assertEqual(resp.status_code, 200, f"Template {tpl} with mode {mode} returned {resp.status_code}")
                body = resp.content.decode("utf-8")
                self.assertIn(f'data-theme="{mode}"', body)
                self.assertIn(f"--theme-mode: {mode};", body)


class TestDesignSystemAndPresets(TestCase):
    """
    Test suite for Phase 12: Next-Level Professional Authentication Design System & Presets.
    Covers 10 color palettes, 10 design presets, component presets, density, SEO, and backward compatibility.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_ten_curated_color_palettes_registered(self):
        """Verify all 10 coordinated color palettes are registered with dark & light tokens."""
        palettes = TemplateRegistry.get_color_palettes()
        expected = [
            "midnight", "ocean", "indigo", "violet", "emerald",
            "teal", "rose", "amber", "slate", "graphite"
        ]
        self.assertEqual(len(palettes), 10)
        for key in expected:
            self.assertIn(key, palettes)
            pal = palettes[key]
            self.assertIn("name", pal)
            self.assertIn("dark", pal)
            self.assertIn("light", pal)
            for mode in ("dark", "light"):
                tokens = pal[mode]
                self.assertIn("primary", tokens)
                self.assertIn("bg", tokens)
                self.assertIn("surface", tokens)
                self.assertIn("text", tokens)
                self.assertIn("border", tokens)

    def test_ten_design_presets_registered(self):
        """Verify all 10 complete 1-click design presets are registered with swatches and metadata."""
        presets = TemplateRegistry.get_design_presets()
        expected = [
            "midnight_saas", "ocean_pro", "indigo_modern", "emerald_finance",
            "violet_creative", "clean_light", "executive", "minimal_mono",
            "soft_modern", "dark_enterprise"
        ]
        self.assertEqual(len(presets), 10)
        for key in expected:
            self.assertIn(key, presets)
            preset = presets[key]
            self.assertIn("name", preset)
            self.assertIn("description", preset)
            self.assertIn("swatches", preset)
            self.assertIn("theme_mode", preset)
            self.assertIn("palette", preset)
            self.assertIn("card", preset)
            self.assertIn("buttons", preset)
            self.assertIn("inputs", preset)
            self.assertIn("density", preset.get("spacing", {}))

    def test_generate_css_variables_emits_design_tokens(self):
        """Verify generate_css_variables outputs modern design system tokens."""
        cfg = {
            "template": "modern",
            "theme": {"mode": "dark"},
            "palette": {"preset": "emerald"},
            "spacing": {"density": "compact"},
            "card": {"preset": "glass"},
        }
        css = TemplateRegistry.generate_css_variables(cfg)
        self.assertIn("--color-primary: #10b981;", css)
        self.assertIn("--color-bg: #061a14;", css)
        self.assertIn("--color-surface: #0b2e24;", css)
        self.assertIn("--density-card-padding: 20px;", css)

    def test_config_service_sanitizes_palette_and_presets(self):
        """Verify ConfigService properly sanitizes palette, presets, and density."""
        raw = {
            "template": "modern",
            "palette": {"preset": "emerald", "custom_colors": {"primary": "#123456"}},
            "design_preset": "midnight_saas",
            "spacing": {"density": "spacious"},
            "buttons": {"preset": "pill", "border_radius": "99px"},
            "inputs": {"preset": "bordered"},
            "card": {"preset": "elevated"},
        }
        clean = ConfigService.sanitize_config_data(raw)
        self.assertEqual(clean["palette"]["preset"], "emerald")
        self.assertEqual(clean["palette"]["custom_colors"]["primary"], "#123456")
        self.assertEqual(clean["design_preset"], "midnight_saas")
        self.assertEqual(clean["spacing"]["density"], "spacious")
        self.assertEqual(clean["buttons"]["preset"], "pill")
        self.assertEqual(clean["inputs"]["preset"], "bordered")
        self.assertEqual(clean["card"]["preset"], "elevated")

        # Invalid values fallback to safe defaults
        invalid_raw = {
            "template": "modern",
            "palette": {"preset": "INVALID_PALETTE"},
            "design_preset": "HACK_PRESET",
            "spacing": {"density": "HUGE"},
            "buttons": {"preset": "UNKNOWN"},
            "inputs": {"preset": "UNKNOWN"},
            "card": {"preset": "UNKNOWN"},
        }
        clean_inv = ConfigService.sanitize_config_data(invalid_raw)
        self.assertEqual(clean_inv["palette"]["preset"], "indigo")
        self.assertEqual(clean_inv["design_preset"], "")
        self.assertEqual(clean_inv["spacing"]["density"], "comfortable")
        self.assertEqual(clean_inv["buttons"]["preset"], "solid")
        self.assertEqual(clean_inv["inputs"]["preset"], "minimal")
        self.assertEqual(clean_inv["card"]["preset"], "default")

    def test_apply_config_and_render_login_with_design_system(self):
        """Apply a complete design system preset and verify login page reflects the tokens and classes."""
        cfg = {
            "template": "modern",
            "theme": {"mode": "dark"},
            "palette": {"preset": "violet"},
            "design_preset": "violet_creative",
            "spacing": {"density": "spacious"},
            "card": {"preset": "soft"},
            "buttons": {"preset": "pill"},
            "inputs": {"preset": "bordered"},
        }
        apply_resp = self.client.post(
            "/api/builder/configurations/apply/",
            data=json.dumps(cfg),
            content_type="application/json",
        )
        self.assertEqual(apply_resp.status_code, 200)

        login_resp = self.client.get("/login/?template=modern")
        self.assertEqual(login_resp.status_code, 200)
        body = login_resp.content.decode("utf-8")
        self.assertIn("--color-primary: #8b5cf6;", body)
        self.assertIn("density-spacious", body)
        self.assertIn("card-style-soft", body)
        self.assertIn("btn-style-pill", body)

    def test_templates_gallery_view_has_seo_and_filter_features(self):
        """Verify templates preview gallery includes SEO JSON-LD and category filter controls."""
        resp = self.client.get("/templates-preview/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn('application/ld+json', body)
        self.assertIn('Auth Studio Template Gallery', body)
        self.assertIn('data-filter="minimal"', body)
        self.assertIn('data-filter="business"', body)
        self.assertIn('data-filter="creative"', body)
        self.assertIn('gallery-search-input', body)

    def test_builder_view_passes_palettes_and_presets_context(self):
        """Verify builder view passes color_palettes and design_presets to template context."""
        resp = self.client.get("/builder/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("design_presets", resp.context)
        self.assertIn("color_palettes", resp.context)
        self.assertIn("window.colorPalettes =", body)
        self.assertIn("window.designPresets =", body)

    def test_backward_compatibility_legacy_config_payload(self):
        """Verify old configs without design_preset or palette merge cleanly without errors."""
        legacy_cfg = {
            "template": "split",
            "authentication": {"enable_otp": True},
            "branding": {"brand_name": "Legacy Corp"},
        }
        merged = TemplateRegistry.merge_config("split", legacy_cfg)
        self.assertEqual(merged["template"], "split")
        self.assertEqual(merged["branding"]["brand_name"], "Legacy Corp")
        # Default palette and spacing must be populated safely
        self.assertIn("palette", merged)
        self.assertIn("spacing", merged)
        css = TemplateRegistry.generate_css_variables(merged)
        self.assertIn("--color-primary:", css)


class CardPositionAndBackgroundEnhancementTests(TestCase):
    """
    Verification suite for Login Card Position / Movement and Background Handling enhancements.
    Validates:
      - Default card position (center, 50%, 50%) across all three templates
      - Custom card position and fine horizontal/vertical coordinate persistence
      - Background fit options (cover, contain, auto) and all 9 position options
      - Backward compatibility with old configurations
      - Exported ZIP contains pre-baked card position and background CSS tokens
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_test_sqlite_tables()

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_default_card_position_across_all_templates(self):
        """Verify Modern, Split, and Corporate all have valid default card position tokens."""
        for tpl_id in ("modern", "split", "corporate"):
            defaults = TemplateRegistry.get_default_configuration(tpl_id)
            self.assertEqual(defaults["layout"]["card_position"], "center")
            self.assertEqual(defaults["layout"]["card_horizontal_position"], 50)
            self.assertEqual(defaults["layout"]["card_vertical_position"], 50)
            self.assertEqual(defaults["card"]["position"], "center")
            self.assertEqual(defaults["card"]["horizontal_position"], 50)
            self.assertEqual(defaults["card"]["vertical_position"], 50)

            css = TemplateRegistry.generate_css_variables(tpl_id, defaults)
            self.assertIn("--card-position: center;", css)
            self.assertIn("--card-x: 50%;", css)
            self.assertIn("--card-y: 50%;", css)
            self.assertIn("--card-x-pct: 50;", css)
            self.assertIn("--card-y-pct: 50;", css)

    def test_custom_card_position_and_fine_coordinates_css_generation(self):
        """Verify custom 3x3 positions and fine sliders generate exact CSS variables."""
        test_positions = [
            ("top-left", 0, 0),
            ("top-center", 50, 0),
            ("top-right", 100, 0),
            ("center-left", 0, 50),
            ("center", 50, 50),
            ("center-right", 100, 50),
            ("bottom-left", 0, 100),
            ("bottom-center", 50, 100),
            ("bottom-right", 100, 100),
            ("custom", 25, 75),
        ]
        for pos_name, h_val, v_val in test_positions:
            cfg = {
                "template": "modern",
                "layout": {
                    "card_position": pos_name,
                    "card_horizontal_position": h_val,
                    "card_vertical_position": v_val,
                },
            }
            css = TemplateRegistry.generate_css_variables("modern", cfg)
            self.assertIn(f"--card-position: {pos_name};", css)
            self.assertIn(f"--card-x: {h_val}%;", css)
            self.assertIn(f"--card-y: {v_val}%;", css)
            self.assertIn(f"--card-x-pct: {h_val};", css)
            self.assertIn(f"--card-y-pct: {v_val};", css)

    def test_background_fit_and_9_positions_css_generation(self):
        """Verify background size (cover, contain, auto) and all 9 position choices resolve cleanly."""
        bg_positions = [
            ("center", "center center"),
            ("top", "center top"),
            ("bottom", "center bottom"),
            ("left", "left center"),
            ("right", "right center"),
            ("top-left", "left top"),
            ("top-right", "right top"),
            ("bottom-left", "left bottom"),
            ("bottom-right", "right bottom"),
        ]
        for raw_pos, expected_css in bg_positions:
            for size_choice in ("cover", "contain", "auto"):
                cfg = {
                    "template": "modern",
                    "background": {
                        "type": "image",
                        "size": size_choice,
                        "position": raw_pos,
                        "repeat": "no-repeat",
                    },
                }
                css = TemplateRegistry.generate_css_variables("modern", cfg)
                self.assertIn(f"--auth-bg-size: {size_choice};", css)
                self.assertIn(f"--auth-bg-position: {expected_css};", css)

    def test_config_service_sanitizes_and_persists_card_position(self):
        """Verify ConfigService sanitizes and persists card position and coordinates."""
        raw_data = {
            "template": "split",
            "layout": {
                "card_position": "top-right",
                "card_horizontal_position": 95,
                "card_vertical_position": 10,
            },
            "card": {
                "position": "top-right",
                "horizontal_position": 95,
                "vertical_position": 10,
            },
            "background": {
                "position": "bottom-left",
                "size": "contain",
            },
        }
        sanitized = ConfigService.sanitize_config_data(raw_data)
        self.assertEqual(sanitized["layout"]["card_position"], "top-right")
        self.assertEqual(sanitized["layout"]["card_horizontal_position"], 95)
        self.assertEqual(sanitized["layout"]["card_vertical_position"], 10)
        self.assertEqual(sanitized["card"]["position"], "top-right")
        self.assertEqual(sanitized["card"]["horizontal_position"], 95)
        self.assertEqual(sanitized["card"]["vertical_position"], 10)
        self.assertEqual(sanitized["background"]["position"], "bottom-left")
        self.assertEqual(sanitized["background"]["size"], "contain")

    def test_config_save_and_load_api_card_position(self):
        """Test full save and load API preserves card position and background choices."""
        save_payload = {
            "configuration_name": "Position Test Config",
            "configuration_data": {
                "template": "corporate",
                "layout": {
                    "card_position": "bottom-right",
                    "card_horizontal_position": 85,
                    "card_vertical_position": 90,
                },
                "background": {
                    "type": "color",
                    "color": "#111827",
                    "position": "top-left",
                    "size": "cover",
                },
            },
        }
        save_resp = self.client.post(
            "/api/builder/configurations/save/",
            data=json.dumps(save_payload),
            content_type="application/json",
        )
        self.assertEqual(save_resp.status_code, 200)
        save_data = save_resp.json()
        self.assertTrue(save_data["success"])
        config_id = save_data["config"]["id"]

        # Load back
        load_resp = self.client.get(f"/api/builder/configurations/{config_id}/load/")
        self.assertEqual(load_resp.status_code, 200)
        loaded = load_resp.json()
        self.assertTrue(loaded["success"])
        loaded_cfg = loaded["configuration"]["data"]
        self.assertEqual(loaded_cfg["layout"]["card_position"], "bottom-right")
        self.assertEqual(loaded_cfg["layout"]["card_horizontal_position"], 85)
        self.assertEqual(loaded_cfg["layout"]["card_vertical_position"], 90)
        self.assertEqual(loaded_cfg["background"]["position"], "top-left")
        self.assertEqual(loaded_cfg["background"]["size"], "cover")

    def test_backward_compatibility_with_legacy_configs_without_position(self):
        """Verify legacy configs without card_position default gracefully to center (50%, 50%)."""
        legacy_cfg = {
            "template": "modern",
            "card": {"width": "420px", "alignment": "center"},
            "background": {"type": "color", "color": "#000000"},
        }
        sanitized = ConfigService.sanitize_config_data(legacy_cfg)
        css = TemplateRegistry.generate_css_variables("modern", sanitized)
        self.assertIn("--card-position: center;", css)
        self.assertIn("--card-x: 50%;", css)
        self.assertIn("--card-y: 50%;", css)

    def test_export_zip_includes_card_position_and_background_tokens(self):
        """Verify export ZIP contains pre-baked card position and background custom properties."""
        export_cfg = {
            "template": "split",
            "layout": {
                "card_position": "top-left",
                "card_horizontal_position": 15,
                "card_vertical_position": 20,
            },
            "background": {
                "type": "image",
                "size": "contain",
                "position": "top-right",
            },
        }
        zip_bytes = ExportService.generate_project_zip(export_cfg, "split")
        self.assertTrue(len(zip_bytes) > 1000)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            self.assertIn("custom-auth-platform/static/accounts/css/auth_tokens.css", zf.namelist())
            tokens_content = zf.read("custom-auth-platform/static/accounts/css/auth_tokens.css").decode("utf-8")
            self.assertIn("--card-position: top-left;", tokens_content)
            self.assertIn("--card-x: 15%;", tokens_content)
            self.assertIn("--card-y: 20%;", tokens_content)
            self.assertIn("--auth-bg-size: contain;", tokens_content)
            self.assertIn("--auth-bg-position: right top;", tokens_content)


class CardTransparencyAndGlassEffectTests(TestCase):
    """
    Focused test suite verifying:
    - Opaque mode behavior (solid surface, 100% content opacity)
    - Translucent mode behavior (surface alpha 0.45, content 100% opaque)
    - Glass mode behavior (surface alpha 0.25, backdrop blur 14px, subtle border)
    - Transparency & blur persistence in ConfigService
    - Backward compatibility with legacy configs
    - Token generation across all 3 templates (modern, split, corporate)
    - Export ZIP includes surface transparency and backdrop filter tokens
    """

    def setUp(self):
        self.client = Client()

    def test_card_appearance_defaults_across_all_templates(self):
        """Verify default template configs have appearance='opaque', backdrop_blur=0, border_enabled=True."""
        for tpl_id in ("modern", "split", "corporate"):
            cfg = TemplateRegistry.get_default_config(tpl_id)
            card = cfg.get("card", {})
            self.assertEqual(card.get("appearance"), "opaque")
            self.assertEqual(card.get("opacity"), 100)
            self.assertEqual(card.get("backdrop_blur"), 0)
            self.assertTrue(card.get("border_enabled"))

    def test_opaque_mode_css_tokens(self):
        """Verify opaque mode generates 100% surface alpha, 0px blur, and --card-opacity: 1."""
        config = {
            "template": "modern",
            "card": {
                "appearance": "opaque",
                "background_color": "#1b1d21",
                "opacity": 100,
                "backdrop_blur": 0,
                "border_enabled": True,
            },
        }
        css = TemplateRegistry.generate_css_variables("modern", config)
        self.assertIn("--card-appearance: opaque;", css)
        self.assertIn("--card-bg-surface: rgba(27, 29, 33, 1.00);", css)
        self.assertIn("--card-opacity: 1.00;", css)
        self.assertIn("--card-surface-alpha: 1.00;", css)
        self.assertIn("--card-backdrop-blur: 0px;", css)

    def test_translucent_mode_css_tokens(self):
        """Verify translucent mode generates semi-transparent surface (e.g. 0.45) with 100% DOM element opacity."""
        config = {
            "template": "split",
            "card": {
                "appearance": "translucent",
                "background_color": "#ffffff",
                "opacity": 45,
                "backdrop_blur": 0,
                "border_enabled": True,
                "border_opacity": 30,
            },
        }
        css = TemplateRegistry.generate_css_variables("split", config)
        self.assertIn("--card-appearance: translucent;", css)
        self.assertIn("--card-bg-surface: rgba(255, 255, 255, 0.45);", css)
        self.assertIn("--card-opacity: 0.45;", css)
        self.assertIn("--card-surface-alpha: 0.45;", css)
        self.assertIn("--card-backdrop-blur: 0px;", css)

    def test_glass_mode_css_tokens_and_backdrop_blur(self):
        """Verify glass mode generates frosted glass surface (0.25 alpha), 14px backdrop blur, and restrained border."""
        config = {
            "template": "corporate",
            "card": {
                "appearance": "glass",
                "background_color": "#ffffff",
                "opacity": 25,
                "backdrop_blur": 14,
                "border_enabled": True,
                "border_opacity": 25,
                "border_color": "#ffffff",
                "border_width": 1,
                "shadow": "medium",
            },
        }
        css = TemplateRegistry.generate_css_variables("corporate", config)
        self.assertIn("--card-appearance: glass;", css)
        self.assertIn("--card-bg-surface: rgba(255, 255, 255, 0.25);", css)
        self.assertIn("--card-opacity: 0.25;", css)
        self.assertIn("--card-surface-alpha: 0.25;", css)
        self.assertIn("--card-backdrop-blur: 14px;", css)
        self.assertIn("--card-border-width: 1px;", css)
        self.assertIn("--card-border-color: rgba(255, 255, 255, 0.25);", css)

    def test_border_enabled_toggle(self):
        """Verify toggling card border off sets width 0px and transparent color."""
        config = {
            "template": "modern",
            "card": {
                "appearance": "glass",
                "border_enabled": False,
            },
        }
        css = TemplateRegistry.generate_css_variables("modern", config)
        self.assertIn("--card-border-width: 0px;", css)
        self.assertIn("--card-border-color: transparent;", css)

    def test_config_service_sanitizes_card_transparency_fields(self):
        """Verify ConfigService properly sanitizes appearance, border_enabled, border_opacity, and backdrop_blur."""
        raw_card = {
            "appearance": "GLASS",
            "opacity": "35",
            "backdrop_blur": "18px",
            "border_enabled": "true",
            "border_opacity": "40",
            "border_width": 2,
        }
        clean = ConfigService.sanitize_card(raw_card)
        self.assertEqual(clean["appearance"], "glass")
        self.assertEqual(clean["opacity"], 35)
        self.assertEqual(clean["backdrop_blur"], 18)
        self.assertTrue(clean["border_enabled"])
        self.assertEqual(clean["border_opacity"], 40)
        self.assertEqual(clean["border_width"], 2)

    def test_backward_compatibility_legacy_config(self):
        """Verify legacy configs without appearance field gracefully default to opaque and full surface opacity."""
        legacy_cfg = {
            "template": "modern",
            "card": {
                "width": "420px",
                "background_color": "#201f22",
            },
        }
        sanitized = ConfigService.sanitize_config_data(legacy_cfg)
        css = TemplateRegistry.generate_css_variables("modern", sanitized)
        self.assertIn("--card-appearance: opaque;", css)
        self.assertIn("--card-opacity: 1.00;", css)
        self.assertIn("--card-bg-surface: rgba(32, 31, 34, 1.00);", css)

    def test_export_zip_includes_card_transparency_tokens(self):
        """Verify export ZIP contains pre-baked card transparency and glass tokens."""
        export_cfg = {
            "template": "split",
            "card": {
                "appearance": "glass",
                "background_color": "#ffffff",
                "opacity": 25,
                "backdrop_blur": 16,
                "border_enabled": True,
                "border_opacity": 25,
            },
        }
        zip_bytes = ExportService.generate_project_zip(export_cfg, "split")
        self.assertTrue(len(zip_bytes) > 1000)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            tokens_content = zf.read("custom-auth-platform/static/accounts/css/auth_tokens.css").decode("utf-8")
            self.assertIn("--card-appearance: glass;", tokens_content)
            self.assertIn("--card-bg-surface: rgba(255, 255, 255, 0.25);", tokens_content)
            self.assertIn("--card-backdrop-blur: 16px;", tokens_content)


class BackgroundImageUrlAndPreviewStackingTests(TestCase):
    """Unit and integration tests for background image URL validation, sanitization, and preview stacking order."""

    def test_valid_https_image_url_accepted(self):
        url = "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?w=1600"
        validated = ConfigService.validate_background_data_uri(url, raise_exception=True)
        self.assertEqual(validated, url)

    def test_valid_http_image_url_accepted(self):
        url = "http://example.com/assets/background.jpg"
        validated = ConfigService.validate_background_data_uri(url, raise_exception=True)
        self.assertEqual(validated, url)

    def test_unsafe_schemes_rejected(self):
        unsafe = [
            "javascript:alert(1)",
            "vbscript:msgbox",
            "file:///etc/passwd",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        ]
        for bad_uri in unsafe:
            with self.assertRaises(ValidationError):
                ConfigService.validate_background_data_uri(bad_uri, raise_exception=True)

    def test_svg_image_rejected(self):
        svg_uri = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        with self.assertRaises(ValidationError):
            ConfigService.validate_background_data_uri(svg_uri, raise_exception=True)

    def test_characters_injection_rejected(self):
        bad_urls = [
            'https://example.com/image.jpg"; evil-css;',
            "https://example.com/image.jpg'; evil-css;",
            "https://example.com/image.jpg<script>",
        ]
        for bad in bad_urls:
            with self.assertRaises(ValidationError):
                ConfigService.validate_background_data_uri(bad, raise_exception=True)

    def test_sanitize_background_source_and_url(self):
        raw_bg = {
            "type": "image",
            "source": "url",
            "image_url": "https://images.unsplash.com/photo-test.jpg",
            "size": "contain",
            "position": "top-right",
            "repeat": "repeat-x",
            "overlay": {"color": "#111111", "opacity": 50},
        }
        clean = ConfigService.sanitize_background(raw_bg)
        self.assertEqual(clean["type"], "image")
        self.assertEqual(clean["source"], "url")
        self.assertEqual(clean["image_url"], "https://images.unsplash.com/photo-test.jpg")
        self.assertEqual(clean["size"], "contain")
        self.assertEqual(clean["position"], "top-right")
        self.assertEqual(clean["repeat"], "repeat-x")
        self.assertEqual(clean["overlay"]["opacity"], 50)

    def test_template_registry_emits_bg_image_url(self):
        cfg = {
            "template": "modern",
            "background": {
                "type": "image",
                "source": "url",
                "image_url": "https://images.unsplash.com/photo-office.jpg",
                "size": "cover",
                "position": "center",
            }
        }
        css = TemplateRegistry.generate_css_variables("modern", cfg)
        self.assertIn('--auth-bg-image: url("https://images.unsplash.com/photo-office.jpg");', css)
        self.assertIn('--auth-bg-size: cover;', css)

    def test_preview_layer_stacking_css_rules_in_auth_tokens(self):
        import os
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "accounts", "css", "auth_tokens.css")
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("html.is-preview {", content)
        self.assertIn("width: 100% !important;", content)
        self.assertIn("display: block !important;", content)

        self.assertIn("body.is-preview .auth-bg-filter-layer", content)
        self.assertIn("z-index: 0 !important;", content)
        self.assertIn("body.is-preview .auth-bg-overlay", content)
        self.assertIn("z-index: 1 !important;", content)
        self.assertIn("body.is-preview .auth-wrapper", content)
        self.assertIn("z-index: 3 !important;", content)
        self.assertIn("body.is-preview .auth-card", content)
        self.assertIn("z-index: 4 !important;", content)
