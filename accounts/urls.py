from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("reset-password/", views.reset_password_view, name="reset_password"),
    path("api/otp/request/", views.otp_request_api, name="otp_request"),
    path("api/otp/verify/", views.otp_verify_api, name="otp_verify"),
    path("api/register/otp/verify/", views.register_otp_verify_api, name="register_otp_verify"),
    path("api/register/otp/resend/", views.register_otp_resend_api, name="register_otp_resend"),
    path("api/forgot-password/otp/request/", views.forgot_password_otp_request_api, name="forgot_password_otp_request"),
    path("api/forgot-password/otp/verify/", views.forgot_password_otp_verify_api, name="forgot_password_otp_verify"),
    path("api/forgot-password/otp/resend/", views.forgot_password_otp_resend_api, name="forgot_password_otp_resend"),
    path("api/reset-password/", views.reset_password_api, name="reset_password_api"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("logout/", views.logout_view, name="logout"),
    path("templates-preview/", views.templates_preview_view, name="templates_preview"),
    path("builder/", views.builder_view, name="builder"),
    path("api/builder/configurations/", views.config_list_api, name="config_list_api"),
    path("api/builder/configurations/save/", views.config_save_api, name="config_save_api"),
    path("api/builder/configurations/<int:config_id>/load/", views.config_load_api, name="config_load_api"),
    path("api/builder/configurations/<int:config_id>/duplicate/", views.config_duplicate_api, name="config_duplicate_api"),
    path("api/builder/configurations/<int:config_id>/delete/", views.config_delete_api, name="config_delete_api"),
    path("api/builder/configurations/apply/", views.config_apply_api, name="config_apply_api"),
    path("api/builder/configurations/reset/", views.config_reset_api, name="config_reset_api"),
    path("api/builder/export-zip/", views.export_zip_api, name="export_zip_api"),
]
