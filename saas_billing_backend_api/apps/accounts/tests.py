from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User
from apps.billing.models import Plan


class AccountsTests(APITestCase):

    def setUp(self):
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.me_url = reverse("me")
        self.logout_url = reverse("logout")

        self.password = "StrongPassword123"

        self.free_plan = Plan.objects.create(
            code="FREE",
            name="Free",
            description="Free plan",
            monthly_price=0,
            annual_price=0,
            api_request_limit=1000,
            is_active=True,
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password=self.password,
            first_name="Test",
            last_name="User",
        )

    # =========================================================
    # REGISTRATION
    # =========================================================

    def test_register_user_successfully(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "newuser@example.com",
                "password": self.password,
                "first_name": "New",
                "last_name": "User",
                "organization_name": "New Organization",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            User.objects.filter(
                email="newuser@example.com"
            ).exists()
        )

        self.assertEqual(
            response.data["message"],
            "Registration successful.",
        )

        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_register_duplicate_email_fails(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "user@example.com",
                "password": self.password,
                "first_name": "Duplicate",
                "last_name": "User",
                "organization_name": "Duplicate Organization",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_register_email_is_normalized(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "  NEWUSER@EXAMPLE.COM  ",
                "password": self.password,
                "first_name": "New",
                "last_name": "User",
                "organization_name": "Normalized Organization",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            User.objects.filter(
                email="newuser@example.com"
            ).exists()
        )

    def test_register_requires_organization_name(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "noorg@example.com",
                "password": self.password,
                "first_name": "No",
                "last_name": "Organization",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "organization_name",
            response.data,
        )

    # =========================================================
    # LOGIN
    # =========================================================

    def test_login_successfully(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "user@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["message"],
            "Login successful.",
        )

        self.assertIn(
            "tokens",
            response.data,
        )

        self.assertIn(
            "access",
            response.data["tokens"],
        )

        self.assertIn(
            "refresh",
            response.data["tokens"],
        )

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "user@example.com",
                "password": "WrongPassword123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_login_nonexistent_user_returns_401(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "doesnotexist@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # =========================================================
    # ME
    # =========================================================

    def test_me_requires_authentication(self):
        response = self.client.get(
            self.me_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_can_access_me(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.get(
            self.me_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["email"],
            "user@example.com",
        )

    # =========================================================
    # JWT
    # =========================================================

    def test_login_returns_valid_jwt_tokens(self):
        login_response = self.client.post(
            self.login_url,
            {
                "email": "user@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        access_token = login_response.data["tokens"]["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get(
            self.me_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["email"],
            "user@example.com",
        )

    # =========================================================
    # LOGOUT
    # =========================================================

    def test_logout_successfully(self):
        login_response = self.client.post(
            self.login_url,
            {
                "email": "user@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        access_token = login_response.data["tokens"]["access"]
        refresh_token = login_response.data["tokens"]["refresh"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.post(
            self.logout_url,
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["message"],
            "Logout successful.",
        )

    def test_logout_requires_authentication(self):
        response = self.client.post(
            self.logout_url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )