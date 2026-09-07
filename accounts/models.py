from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class AuthUser(models.Model):
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=150, blank=True, null=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254, unique=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    password = models.CharField(max_length=128)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.IntegerField(default=1)
    is_staff = models.IntegerField(default=0)
    is_superuser = models.IntegerField(default=0)
    last_login = models.DateTimeField(blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "auth_user"

    def __str__(self):
        return self.username or self.email or f"User #{self.id}"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_username(self):
        return self.username

    def get_full_name(self):
        if self.full_name:
            return self.full_name
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.username

    def get_session_auth_hash(self):
        from django.utils.crypto import salted_hmac
        key_salt = "accounts.models.AuthUser.get_session_auth_hash"
        return salted_hmac(key_salt, self.password or "", algorithm="sha256").hexdigest()

    def set_password(self, raw_password):
        """
        Generates a standard Django pbkdf2_sha256 hash.
        Populates both `password` (128 char) and `password_hash` (255 char)
        to maintain 100% compatibility with existing company database conventions.
        """
        hashed = make_password(raw_password)
        self.password = hashed
        self.password_hash = hashed

    def check_password(self, raw_password):
        """
        Verifies raw password against the stored pbkdf2_sha256 hash.
        Checks against `password` first, then falls back to `password_hash`.
        """
        if self.password and check_password(raw_password, self.password):
            return True
        if self.password_hash and check_password(raw_password, self.password_hash):
            return True
        return False


class AuthOtps(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        AuthUser,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        blank=True,
        null=True,
    )
    identifier = models.CharField(max_length=255)
    purpose = models.CharField(max_length=50)
    otp_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    is_used = models.IntegerField(default=0)
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "auth_otps"

    def __str__(self):
        return f"OTP for {self.identifier} ({self.purpose})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid_for_attempt(self):
        return not bool(self.is_used) and not self.is_expired and self.attempt_count < 5


class AuthConfigurations(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        AuthUser,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        blank=True,
        null=True,
    )
    builder_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    configuration_name = models.CharField(max_length=255)
    landing_url = models.TextField(blank=True, null=True)
    redirect_url = models.TextField(blank=True, null=True)
    configuration_data = models.JSONField(default=dict)
    is_active = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "auth_configurations"

    def __str__(self):
        return self.configuration_name


class LoginConfiguration(models.Model):
    id = models.AutoField(primary_key=True)
    configuration_name = models.CharField(max_length=255)
    configuration_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    zip_file = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "login_configuration"

    def __str__(self):
        return self.configuration_name


class Users(models.Model):
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    configuration = models.ForeignKey(
        LoginConfiguration,
        on_delete=models.DO_NOTHING,
        db_column="configuration_id",
    )

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self):
        return self.full_name or self.email

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)