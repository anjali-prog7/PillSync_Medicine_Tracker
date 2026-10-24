from django.test import TestCase
from rest_framework.test import APIClient

from .models import User


class ProfileEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="9876543210",
            first_name="Jane",
            last_name="Doe",
            password="TestPass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_profile_get_returns_real_user_data(self):
        response = self.client.get("/api/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["phone"], "9876543210")
        self.assertEqual(data["full_name"], "Jane Doe")
        self.assertEqual(data["role"], "Patient")
        self.assertEqual(data["role_code"], "PATIENT")
        self.assertTrue(data["is_active"])
        self.assertIsNotNone(data["date_joined"])

    def test_profile_get_requires_auth(self):
        anon = APIClient()
        response = anon.get("/api/accounts/profile/")
        self.assertEqual(response.status_code, 401)

    def test_profile_update_persists_full_name_email_phone(self):
        response = self.client.patch(
            "/api/accounts/profile/",
            {
                "full_name": "Janet Doe-Smith",
                "email": "janet@example.com",
                "phone": "+919123456789",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["full_name"], "Janet Doe-Smith")
        self.assertEqual(response.data["email"], "janet@example.com")
        # +91 prefix is stripped and stored as a 10-digit number.
        self.assertEqual(response.data["phone"], "9123456789")

        # Persisted in the database, not just in the response.
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Janet")
        self.assertEqual(self.user.last_name, "Doe-Smith")
        self.assertEqual(self.user.email, "janet@example.com")
        self.assertEqual(self.user.phone, "9123456789")

    def test_profile_update_rejects_duplicate_phone(self):
        User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            phone="9000000000",
            password="TestPass123",
        )
        response = self.client.patch(
            "/api/accounts/profile/",
            {"phone": "9000000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)

    def test_profile_update_clears_phone_when_blank(self):
        response = self.client.patch(
            "/api/accounts/profile/", {"phone": ""}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["phone"])

    def test_profile_update_rejects_invalid_phone(self):
        response = self.client.patch(
            "/api/accounts/profile/", {"phone": "123"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)

    def test_profile_get_returns_gender_dob_and_verification(self):
        response = self.client.get("/api/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        # New profile fields are present with sane defaults (not hardcoded).
        self.assertIn("gender", data)
        self.assertIn("gender_code", data)
        self.assertIn("date_of_birth", data)
        self.assertIn("is_verified", data)
        self.assertIsNone(data["gender"])
        self.assertIsNone(data["date_of_birth"])
        self.assertFalse(data["is_verified"])

    def test_profile_update_persists_gender_and_dob(self):
        response = self.client.patch(
            "/api/accounts/profile/",
            {"gender": "FEMALE", "date_of_birth": "1992-04-23"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # API returns the human-readable label and the ISO date.
        self.assertEqual(response.data["gender"], "Female")
        self.assertEqual(response.data["gender_code"], "FEMALE")
        self.assertEqual(response.data["date_of_birth"], "1992-04-23")

        # Persisted in the database, not just in the response.
        self.user.refresh_from_db()
        self.assertEqual(self.user.gender, "FEMALE")
        self.assertEqual(self.user.date_of_birth.isoformat(), "1992-04-23")

    def test_profile_update_rejects_invalid_gender(self):
        response = self.client.patch(
            "/api/accounts/profile/", {"gender": "ALIEN"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("gender", response.data)

    def test_profile_update_clears_gender_and_dob_when_blank(self):
        self.user.gender = "MALE"
        self.user.date_of_birth = "1992-04-23"
        self.user.save()

        response = self.client.patch(
            "/api/accounts/profile/",
            {"gender": "", "date_of_birth": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["gender"])
        self.assertIsNone(response.data["date_of_birth"])

        self.user.refresh_from_db()
        self.assertIsNone(self.user.gender)
        self.assertIsNone(self.user.date_of_birth)

    def test_profile_get_returns_last_login_from_django(self):
        from django.utils import timezone

        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])
        response = self.client.get("/api/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["last_login"])


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="9876543210",
            password="OldPass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        response = self.client.post(
            "/api/accounts/change-password/",
            {
                "current_password": "OldPass123",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456"))

    def test_change_password_wrong_current(self):
        response = self.client.post(
            "/api/accounts/change-password/",
            {
                "current_password": "WrongPass",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass123"))

    def test_change_password_mismatch(self):
        response = self.client.post(
            "/api/accounts/change-password/",
            {
                "current_password": "OldPass123",
                "new_password": "NewPass456",
                "confirm_password": "Different789",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_password", response.data)

    def test_change_password_requires_all_fields(self):
        response = self.client.post(
            "/api/accounts/change-password/",
            {"current_password": "OldPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_requires_auth(self):
        anon = APIClient()
        response = anon.post(
            "/api/accounts/change-password/",
            {
                "current_password": "OldPass123",
                "new_password": "NewPass456",
                "confirm_password": "NewPass456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)


class LoginUpdatesLastLoginTests(TestCase):
    """
    Verifies that a real JWT login records the user's last_login (via
    SIMPLE_JWT's UPDATE_LAST_LOGIN), so the Profile page's "Last Login"
    shows the actual backend value instead of "Not Available".
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            email="login@example.com",
            phone="9876543210",
            password="TestPass123",
        )
        self.client = APIClient()

    def test_token_login_updates_last_login(self):
        # Simulate a previous login long ago, then sign in again.
        from django.utils import timezone
        from datetime import timedelta

        self.user.last_login = timezone.now() - timedelta(days=30)
        self.user.save(update_fields=["last_login"])

        response = self.client.post(
            "/api/token/",
            {"username": "loginuser", "password": "TestPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        # last_login was refreshed to now, not the old 30-day-old value.
        self.assertGreater(
            self.user.last_login,
            timezone.now() - timedelta(minutes=5),
        )

    def test_profile_returns_updated_last_login_after_login(self):
        response = self.client.post(
            "/api/token/",
            {"username": "loginuser", "password": "TestPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        token = response.data["access"]

        # The profile endpoint reports the freshly-updated last_login.
        profile_resp = self.client.get(
            "/api/accounts/profile/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(profile_resp.status_code, 200)
        self.assertIsNotNone(profile_resp.data["last_login"])
