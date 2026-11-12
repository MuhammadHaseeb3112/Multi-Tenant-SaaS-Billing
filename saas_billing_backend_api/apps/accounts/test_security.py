"""
Authentication hardening: login brute-force lockout, per-IP throttles,
refresh token in an httpOnly cookie (rotation, blacklist, logout) and the
Origin check on cookie-authenticated endpoints.
"""

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
)

from apps.billing.models import Plan

from .models import User


COOKIE = "sb_refresh"


class SecurityTestBase(APITestCase):

    def setUp(self):
        Plan.objects.create(
            code="FREE", name="Free", api_request_limit=1000
        )
        self.password = "StrongPassword123"
        self.user = User.objects.create_user(
            email="user@example.com", password=self.password
        )
        self.login_url = reverse("login")
        self.refresh_url = reverse("token_refresh")
        self.logout_url = reverse("logout")
        self.me_url = reverse("me")

    def login(self, password=None, email="user@example.com", **extra):
        return self.client.post(
            self.login_url,
            {"email": email, "password": password or self.password},
            format="json",
            **extra,
        )


class LoginLockoutTests(SecurityTestBase):

    def test_five_failures_lock_the_account_for_that_ip(self):
        for _ in range(5):
            self.assertEqual(
                self.login(password="wrong").status_code,
                status.HTTP_401_UNAUTHORIZED,
            )

        # Even the correct password is refused while locked.
        response = self.login()

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertIn("Retry-After", response)
        self.assertNotIn(COOKIE, response.cookies)

    def test_lockout_is_per_ip(self):
        for _ in range(5):
            self.login(password="wrong")

        response = self.login(REMOTE_ADDR="10.0.0.99")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_email_is_case_insensitive_for_lockout(self):
        for _ in range(5):
            self.login(password="wrong", email="USER@example.com")

        self.assertEqual(
            self.login().status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_distributed_guessing_on_one_email_is_stopped(self):
        for i in range(3):
            self.login(password="wrong", REMOTE_ADDR=f"10.0.0.{i}")

        response = self.login(REMOTE_ADDR="10.0.0.200")

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )

    def test_successful_login_resets_the_counter(self):
        for _ in range(4):
            self.login(password="wrong")

        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

        for _ in range(4):
            self.login(password="wrong")

        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_other_accounts_are_not_affected(self):
        User.objects.create_user(
            email="other@example.com", password=self.password
        )
        for _ in range(5):
            self.login(password="wrong")

        self.assertEqual(
            self.login(email="other@example.com").status_code,
            status.HTTP_200_OK,
        )


class AuthThrottleTests(SecurityTestBase):

    def test_login_endpoint_is_rate_limited_per_ip(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import SimpleRateThrottle

        rates = dict(api_settings.DEFAULT_THROTTLE_RATES, auth="3/min")

        with self.settings(
            LOGIN_MAX_FAILURES_PER_IP_EMAIL=100
        ), _patched_rates(SimpleRateThrottle, rates):
            codes = [
                self.login(password="wrong").status_code for _ in range(4)
            ]

        self.assertEqual(codes[:3], [401, 401, 401])
        self.assertEqual(codes[3], status.HTTP_429_TOO_MANY_REQUESTS)


class _patched_rates:
    """Temporarily replace DRF throttle rates (read at class level)."""

    def __init__(self, cls, rates):
        self.cls = cls
        self.rates = rates

    def __enter__(self):
        self.old = self.cls.THROTTLE_RATES
        self.cls.THROTTLE_RATES = self.rates

    def __exit__(self, *exc):
        self.cls.THROTTLE_RATES = self.old


class RefreshCookieTests(SecurityTestBase):

    def test_login_sets_httponly_cookie_scoped_to_auth_path(self):
        response = self.login()

        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/auth/")
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertNotIn("refresh", response.data["tokens"])

    def test_refresh_uses_cookie_and_rotates_it(self):
        old_cookie = self.login().cookies[COOKIE].value

        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        new_cookie = response.cookies[COOKIE].value
        self.assertNotEqual(new_cookie, old_cookie)

        # The new access token works.
        me = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
        )
        self.assertEqual(me.status_code, status.HTTP_200_OK)

        # The rotated-out refresh token is blacklisted.
        self.client.cookies[COOKIE] = old_cookie
        reused = self.client.post(self.refresh_url)
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_without_cookie_is_401(self):
        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_body_token_is_ignored(self):
        # JS never has the refresh token any more; a token in the body
        # (e.g. stolen and replayed) is not accepted.
        refresh = self.login().cookies[COOKIE].value
        self.client.cookies.clear()

        response = self.client.post(
            self.refresh_url, {"refresh": refresh}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_cookie_is_cleared(self):
        self.client.cookies[COOKIE] = "not-a-token"

        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.cookies[COOKIE].value, "")

    def test_untrusted_origin_cannot_refresh(self):
        self.login()

        response = self.client.post(
            self.refresh_url, HTTP_ORIGIN="https://evil.example.com"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allowed_frontend_origin_can_refresh(self):
        self.login()

        response = self.client.post(
            self.refresh_url, HTTP_ORIGIN="http://localhost:5173"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(JWT_REFRESH_COOKIE_SECURE=True)
    def test_secure_flag_follows_setting(self):
        self.assertTrue(self.login().cookies[COOKIE]["secure"])


class LogoutCookieTests(SecurityTestBase):

    def test_logout_blacklists_cookie_token_and_clears_cookie(self):
        login = self.login()
        access = login.data["tokens"]["access"]

        response = self.client.post(
            self.logout_url, HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[COOKIE].value, "")
        self.assertEqual(BlacklistedToken.objects.count(), 1)

        # The old refresh token can no longer be used.
        self.client.cookies[COOKIE] = login.cookies[COOKIE].value
        self.assertEqual(
            self.client.post(self.refresh_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_with_already_invalid_token_still_succeeds(self):
        access = self.login().data["tokens"]["access"]
        self.client.cookies[COOKIE] = "garbage"

        response = self.client.post(
            self.logout_url, HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
