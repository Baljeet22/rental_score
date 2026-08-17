from django.urls import path

from .views import (
    UserSignupAPIView,
    UserRoleSelectionAPIView,
    UserLoginAPIView,
    UserLogoutAPIView,
    UserEmailVerificationAPIView,
    UserForgotPasswordAPIView,
    UserResetPasswordAPIView,
)

urlpatterns = [
    path(
        "signup/",
        UserSignupAPIView.as_view(),
        name="user-signup",
    ),
    path("login/", UserLoginAPIView.as_view(), name="login"),
    path(
        "login/select-role/",
        UserRoleSelectionAPIView.as_view(),
        name="login-select-role",
    ),
    path("logout/", UserLogoutAPIView.as_view(), name="logout"),
    path(
        "verify-email/",
        UserEmailVerificationAPIView.as_view(),
        name="verify-email",
    ),
    path(
        "forgot-password/",
        UserForgotPasswordAPIView.as_view(),
        name="forgot-password",
    ),
    path(
        "reset-password/",
        UserResetPasswordAPIView.as_view(),
        name="reset-password",
    ),
]
