from django.urls import path

from .account import (
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetValidateView,
)
from .views import (
    CookieTokenRefreshView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)


urlpatterns = [
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),
    path(
        "token/refresh/",
        CookieTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "password/change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "password/reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password/reset/validate/",
        PasswordResetValidateView.as_view(),
        name="password-reset-validate",
    ),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
