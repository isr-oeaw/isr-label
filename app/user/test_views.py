"""Tests for custom user/ HTML views (not allauth; see test_allauth_urls)."""

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from user.models import Role

User = get_user_model()


class UserAuthPagesTests(TestCase):
    def test_signup_get_200(self):
        r = self.client.get(reverse("user-signup"))
        self.assertEqual(r.status_code, 200)

    def test_login_get_200(self):
        r = self.client.get(reverse("account_login"))
        self.assertEqual(r.status_code, 200)

    def test_settings_anonymous_shows_login_page(self):
        r = self.client.get(reverse("user-settings"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "user/login.html")

    def test_settings_200_when_logged_in(self):
        u = User.objects.create_user("su1", "su1@t.local", "p")
        self.client.login(username="su1", password="p")
        r = self.client.get(reverse("user-settings"))
        self.assertEqual(r.status_code, 200)

    def test_profile_200(self):
        u = User.objects.create_user("pu", "pu@t.local", "p")
        self.client.login(username="pu", password="p")
        r = self.client.get(reverse("user-profile"))
        self.assertEqual(r.status_code, 200)

    def test_data_export_requires_login(self):
        r = self.client.get(reverse("data-export"))
        self.assertEqual(r.status_code, 302)

    def test_user_list_requires_staff(self):
        u = User.objects.create_user("ul", "ul@t.local", "p")
        self.client.login(username="ul", password="p")
        r = self.client.get(reverse("user-list"))
        self.assertIn(r.status_code, (302, 403))

    def test_user_management_superuser_200(self):
        su = User.objects.create_superuser("ums", "ums@t.local", "p")
        self.client.login(username="ums", password="p")
        r = self.client.get(reverse("user-management"))
        self.assertEqual(r.status_code, 200)

    def test_user_create_administrator_200(self):
        ad = User.objects.create_user("ued", "ued@t.local", "p")
        r = Role.objects.create(name="Administrator", is_active=True, permissions=[])
        ad.role = r
        ad.save()
        self.client.login(username="ued", password="p")
        r = self.client.get(reverse("user-create"))
        self.assertEqual(r.status_code, 200)

    def test_role_list_200(self):
        su = User.objects.create_superuser("rls", "rls@t.local", "p")
        self.client.login(username="rls", password="p")
        r = self.client.get(reverse("role-list"))
        self.assertEqual(r.status_code, 200)
