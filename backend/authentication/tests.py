from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import User

PASSWORD = "S3cure-Passw0rd!"


def make_user(email="ada@example.com", role=User.Role.CUSTOMER):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Ada", last_name="Obi", role=role
    )


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters between tests
        self.client = APIClient()
        self.url = reverse("auth-register")
        self.payload = {
            "email": "New.User@Example.com",
            "first_name": "New",
            "last_name": "User",
            "phone_number": "+2348012345678",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }

    def test_register_returns_user_and_tokens(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], "new.user@example.com")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_register_always_creates_a_customer(self):
        self.payload["role"] = "admin"  # must be ignored
        self.client.post(self.url, self.payload, format="json")
        self.assertEqual(User.objects.get(email="new.user@example.com").role, User.Role.CUSTOMER)

    def test_register_rejects_mismatched_passwords(self):
        self.payload["password_confirm"] = "something-else-123"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_register_rejects_weak_password(self):
        self.payload["password"] = self.payload["password_confirm"] = "password"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_rejects_duplicate_email_in_any_case(self):
        make_user("new.user@example.com")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_badly_formatted_phone_number(self):
        self.payload["phone_number"] = "08012345678"  # missing +country code
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)


class LoginAndTokenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = make_user()
        self.login_url = reverse("auth-login")

    def login(self, email="ada@example.com", password=PASSWORD):
        return self.client.post(self.login_url, {"email": email, "password": password}, format="json")

    def test_login_returns_tokens_and_profile(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], "customer")
        # The role is also embedded in the access token for the frontend.
        self.assertEqual(AccessToken(response.data["access"])["role"], "customer")

    def test_login_email_is_case_insensitive(self):
        self.assertEqual(self.login(email="ADA@Example.COM").status_code, status.HTTP_200_OK)

    def test_login_with_wrong_password_is_rejected(self):
        self.assertEqual(self.login(password="wrong").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_is_rate_limited(self):
        for _ in range(10):  # the "login" scope allows 10 requests a minute
            self.assertEqual(self.login(password="wrong").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.login(password="wrong").status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_me_requires_a_token(self):
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_unlocks_protected_endpoints(self):
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me = self.client.get(reverse("auth-me"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "ada@example.com")
        # The same token works on another app's endpoint.
        self.assertEqual(self.client.get(reverse("transaction-list")).status_code, status.HTTP_200_OK)

    def test_me_cannot_change_email_or_role(self):
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.patch(
            reverse("auth-me"),
            {"first_name": "Adaeze", "role": "admin", "email": "hacker@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Adaeze")
        self.assertEqual(self.user.role, User.Role.CUSTOMER)
        self.assertEqual(self.user.email, "ada@example.com")

    def test_refresh_rotates_the_token_and_revokes_the_old_one(self):
        old_refresh = self.login().data["refresh"]
        url = reverse("auth-token-refresh")

        refreshed = self.client.post(url, {"refresh": old_refresh}, format="json")
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refreshed.data["refresh"], old_refresh)

        reused = self.client.post(url, {"refresh": old_refresh}, format="json")
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_the_refresh_token(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.client.credentials()  # drop the access token
        refreshed = self.client.post(
            reverse("auth-token-refresh"), {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        response = self.client.post(reverse("auth-logout"), {"refresh": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserModelTests(TestCase):
    def test_email_is_stored_lowercase(self):
        self.assertEqual(make_user("Mixed.Case@Example.com").email, "mixed.case@example.com")

    def test_create_superuser_gets_admin_role(self):
        admin = User.objects.create_superuser(
            email="root@example.com", password=PASSWORD, first_name="Root", last_name="User"
        )
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_role_helper(self):
        self.assertFalse(make_user("c@example.com").is_analyst_or_admin)
        self.assertTrue(make_user("a@example.com", role=User.Role.ANALYST).is_analyst_or_admin)
