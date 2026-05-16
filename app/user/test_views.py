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

    def test_user_management_requires_permission(self):
        u = User.objects.create_user("ul", "ul@t.local", "p")
        self.client.login(username="ul", password="p")
        r = self.client.get(reverse("user-management"))
        self.assertIn(r.status_code, (302, 403))

    def test_user_management_superuser_200(self):
        su = User.objects.create_superuser("ums", "ums@t.local", "p")
        self.client.login(username="ums", password="p")
        r = self.client.get(reverse("user-management"))
        self.assertEqual(r.status_code, 200)

    def test_user_management_administrator_200(self):
        ad = User.objects.create_user("uma", "uma@t.local", "p")
        r = Role.objects.create(name="Administrator", is_active=True, permissions=[])
        ad.role = r
        ad.save()
        self.client.login(username="uma", password="p")
        r = self.client.get(reverse("user-management"))
        self.assertEqual(r.status_code, 200)

    def test_superuser_set_password_get_200(self):
        su = User.objects.create_superuser("supw", "supw@t.local", "p")
        target = User.objects.create_user("tgt", "tgt@t.local", "old-pass-xyz")
        self.client.login(username="supw", password="p")
        url = reverse("user-admin-password", kwargs={"user_id": target.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "user/admin_set_password.html")

    def test_administrator_set_password_forbidden(self):
        ad = User.objects.create_user("admnpw", "admnpw@t.local", "p")
        r = Role.objects.create(name="Administrator", is_active=True, permissions=[])
        ad.role = r
        ad.save()
        target = User.objects.create_user("tgt2", "tgt2@t.local", "p")
        self.client.login(username="admnpw", password="p")
        url = reverse("user-admin-password", kwargs={"user_id": target.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_superuser_set_password_post_updates_login(self):
        su = User.objects.create_superuser("supw2", "supw2@t.local", "p")
        target = User.objects.create_user("tgt3", "tgt3@t.local", "old-secret")
        self.client.login(username="supw2", password="p")
        url = reverse("user-admin-password", kwargs={"user_id": target.pk})
        r = self.client.post(
            url,
            {
                "new_password1": "new-secret-99!",
                "new_password2": "new-secret-99!",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("user-management"))
        self.client.logout()
        self.assertTrue(self.client.login(username="tgt3", password="new-secret-99!"))

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
