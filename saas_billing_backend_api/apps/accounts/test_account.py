"""
Account self-service: profile update, change password, forgot password.
"""

import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.billing.models import Plan
from apps.tenants.models import Membership, Organization

from .models import User

COOKIE = "sb_refresh"
NEW_PASSWORD = "BrandNewPass!789"


@override_settings(FRONTEND_URL="https://app.example.com")
class AccountTestBase(APITestCase):

    def setUp(self):
        cache.clear()
        Plan.objects.create(code="FREE", name="Free", api_request_limit=1000)

        self.password = "StrongPassword123"
        self.user = User.objects.create_user(
            email="user@example.com",
            password=self.password,
            first_name="Old",
            last_name="Name",
        )
        self.organization = Organization.objects.create(
            name="Acme", slug="acme",
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

    def login(self, password=None, client=None):
        return (client or self.client).post(
            reverse("login"),
            {"email": self.user.email, "password": password or self.password},
            format="json",
        )

    def authenticate(self):
        response = self.login()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}"
        )
        return response

    def actions(self):
        return list(
            AuditLog.objects
            .filter(organization=self.organization)
            .values_list("action", flat=True)
        )


class ProfileUpdateTests(AccountTestBase):

    def test_user_updates_own_name(self):
        self.authenticate()

        response = self.client.patch(
            reverse("me"),
            {"first_name": "  Hassan ", "last_name": "Ali"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Hassan")
        self.assertEqual(response.data["last_name"], "Ali")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Hassan")
        self.assertEqual(self.actions(), ["PROFILE_UPDATED"])

    def test_email_cannot_be_changed_here(self):
        self.authenticate()

        self.client.patch(
            reverse("me"),
            {"first_name": "Hassan", "email": "evil@example.com"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "user@example.com")

    def test_blank_first_name_is_rejected(self):
        self.authenticate()

        response = self.client.patch(
            reverse("me"), {"first_name": "   "}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unchanged_name_is_not_logged(self):
        self.authenticate()

        self.client.patch(
            reverse("me"),
            {"first_name": "Old", "last_name": "Name"},
            format="json",
        )

        self.assertEqual(self.actions(), [])

    def test_requires_login(self):
        response = self.client.patch(
            reverse("me"), {"first_name": "X"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeTests(AccountTestBase):

    def change(self, **overrides):
        data = {
            "current_password": self.password,
            "new_password": NEW_PASSWORD,
            "new_password_confirm": NEW_PASSWORD,
        }
        data.update(overrides)
        return self.client.post(
            reverse("password-change"), data, format="json",
        )

    def test_change_password(self):
        self.authenticate()

        response = self.change()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn(COOKIE, response.cookies)

        self.client.credentials()
        self.assertEqual(
            self.login().status_code, status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.login(NEW_PASSWORD).status_code, status.HTTP_200_OK,
        )
        self.assertEqual(self.actions(), ["PASSWORD_CHANGED"])

    def test_other_devices_are_signed_out_but_this_one_stays(self):
        from rest_framework.test import APIClient

        other_device = APIClient()
        self.login(client=other_device)
        old_cookie = other_device.cookies[COOKIE].value

        self.authenticate()
        response = self.change()
        new_cookie = response.cookies[COOKIE].value

        # The other device can no longer refresh its session.
        other_device.cookies[COOKIE] = old_cookie
        self.assertEqual(
            other_device.post(reverse("token_refresh")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # This device got a brand new session.
        self.client.credentials()
        self.client.cookies[COOKIE] = new_cookie
        self.assertEqual(
            self.client.post(reverse("token_refresh")).status_code,
            status.HTTP_200_OK,
        )

    def test_wrong_current_password(self):
        self.authenticate()

        response = self.change(current_password="nope")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_weak_mismatched_or_same_password_is_rejected(self):
        self.authenticate()

        weak = self.change(new_password="123", new_password_confirm="123")
        self.assertIn("new_password", weak.data)

        mismatch = self.change(new_password_confirm="Different!789")
        self.assertIn("new_password_confirm", mismatch.data)

        same = self.change(
            new_password=self.password,
            new_password_confirm=self.password,
        )
        self.assertIn("new_password", same.data)

        for response in (weak, mismatch, same):
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST,
            )

    def test_requires_login_and_trusted_origin(self):
        self.assertEqual(
            self.change().status_code, status.HTTP_401_UNAUTHORIZED,
        )

        self.authenticate()
        response = self.client.post(
            reverse("password-change"),
            {},
            format="json",
            HTTP_ORIGIN="https://evil.example.com",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PasswordResetTests(AccountTestBase):

    def request_reset(self, email="user@example.com"):
        return self.client.post(
            reverse("password-reset"), {"email": email}, format="json",
        )

    def link_parts(self):
        match = re.search(
            r"https://app\.example\.com/reset-password\?uid=(\S+)&token=(\S+)",
            mail.outbox[-1].body,
        )
        self.assertIsNotNone(match)
        return match.group(1), match.group(2)

    def confirm(self, uid, token, password=NEW_PASSWORD):
        return self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": password,
                "new_password_confirm": password,
            },
            format="json",
        )

    def test_reset_email_is_sent_with_a_link(self):
        response = self.request_reset("  USER@example.com ")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["user@example.com"])
        self.link_parts()

    def test_unknown_email_gets_the_same_answer_and_no_email(self):
        known = self.request_reset()
        unknown = self.request_reset("nobody@example.com")

        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.data, known.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_account_gets_no_email(self):
        self.user.is_active = False
        self.user.save()

        self.request_reset()

        self.assertEqual(len(mail.outbox), 0)

    @patch("apps.accounts.account.send_mail", side_effect=OSError("smtp"))
    def test_email_failure_is_not_revealed(self, _mock):
        response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_full_reset_flow(self):
        self.request_reset()
        uid, token = self.link_parts()

        validate = self.client.get(
            reverse("password-reset-validate"),
            {"uid": uid, "token": token},
        )
        self.assertEqual(validate.status_code, status.HTTP_200_OK)

        response = self.confirm(uid, token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            self.login().status_code, status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.login(NEW_PASSWORD).status_code, status.HTTP_200_OK,
        )
        self.assertEqual(self.actions(), ["PASSWORD_RESET"])

    def test_link_works_only_once(self):
        self.request_reset()
        uid, token = self.link_parts()
        self.confirm(uid, token)

        again = self.confirm(uid, token, "AnotherPass!456")

        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.get(
                reverse("password-reset-validate"),
                {"uid": uid, "token": token},
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_bad_link_is_rejected(self):
        self.request_reset()
        uid, token = self.link_parts()

        for bad_uid, bad_token in (
            (uid, token + "x"),
            ("not-a-uid", token),
            ("", ""),
        ):
            response = self.client.get(
                reverse("password-reset-validate"),
                {"uid": bad_uid, "token": bad_token},
            )
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST,
            )

        self.assertEqual(
            self.confirm(uid, token + "x").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(PASSWORD_RESET_TIMEOUT=0)
    def test_expired_link_is_rejected(self):
        self.request_reset()
        uid, token = self.link_parts()

        import time
        time.sleep(1.1)

        self.assertEqual(
            self.confirm(uid, token).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_weak_password_keeps_the_link_usable(self):
        self.request_reset()
        uid, token = self.link_parts()

        weak = self.confirm(uid, token, "123")
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", weak.data)

        self.assertEqual(
            self.confirm(uid, token).status_code, status.HTTP_200_OK,
        )

    def test_reset_signs_out_existing_sessions(self):
        self.login()
        old_cookie = self.client.cookies[COOKIE].value

        self.request_reset()
        uid, token = self.link_parts()
        self.confirm(uid, token)

        self.client.cookies[COOKIE] = old_cookie
        self.assertEqual(
            self.client.post(reverse("token_refresh")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_reset_unlocks_a_locked_out_account(self):
        for _ in range(5):
            self.login("wrong")
        self.assertEqual(
            self.login().status_code, status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.request_reset()
        uid, token = self.link_parts()
        self.confirm(uid, token)

        self.assertEqual(
            self.login(NEW_PASSWORD).status_code, status.HTTP_200_OK,
        )
