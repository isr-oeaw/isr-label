"""URL/view tests for pages app (documentation, announcements)."""

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from .models import Announcement

User = get_user_model()


class DocumentationViewTests(TestCase):
    def test_documentation_anonymous_ok(self):
        r = self.client.get(reverse("documentation"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "documentation.html")


class AnnouncementManagementViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("sua", "sua@t.local", "p")
        self.user = User.objects.create_user("nu", "nu@t.local", "p")

    def test_management_redirects_anonymous(self):
        r = self.client.get(reverse("announcement-management"))
        self.assertEqual(r.status_code, 302)

    def test_management_forbidden_regular_user(self):
        self.client.login(username="nu", password="p")
        r = self.client.get(reverse("announcement-management"))
        self.assertEqual(r.status_code, 403)

    def test_management_ok_superuser(self):
        self.client.login(username="sua", password="p")
        r = self.client.get(reverse("announcement-management"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "pages/announcement_management.html")


class AnnouncementCRUDViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("sud", "sud@t.local", "p")
        self.user = User.objects.create_user("reg", "reg@t.local", "p")
        self.ann = Announcement.objects.create(
            title="T",
            message="M",
            priority="normal",
            created_by=self.admin,
        )

    def test_create_get_redirects_anonymous(self):
        r = self.client.get(reverse("announcement-create"))
        self.assertEqual(r.status_code, 302)

    def test_create_get_ok_superuser(self):
        self.client.login(username="sud", password="p")
        r = self.client.get(reverse("announcement-create"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "pages/announcement_form.html")

    def test_edit_get_ok_superuser(self):
        self.client.login(username="sud", password="p")
        r = self.client.get(
            reverse("announcement-edit", kwargs={"pk": self.ann.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_delete_get_ok_superuser(self):
        self.client.login(username="sud", password="p")
        r = self.client.get(
            reverse("announcement-delete", kwargs={"pk": self.ann.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "pages/announcement_confirm_delete.html")
