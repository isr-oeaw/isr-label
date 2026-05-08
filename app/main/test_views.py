"""Tests for main project views (logs, OpenAPI)."""

from django.test import TestCase, override_settings
from django.urls import reverse


class LogViewTests(TestCase):
    def test_logs_redirect_anonymous(self):
        r = self.client.get(reverse("logs"))
        self.assertEqual(r.status_code, 302)

    def test_logs_403_non_superuser(self):
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_user("lu", "lu@t.local", "p")
        self.client.login(username="lu", password="p")
        r = self.client.get(reverse("logs"))
        self.assertEqual(r.status_code, 403)

    def test_logs_200_superuser(self):
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_superuser("lsu", "lsu@t.local", "p")
        self.client.login(username="lsu", password="p")
        r = self.client.get(reverse("logs"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "main/logs.html")


class OpenAPISchemaTests(TestCase):
    @override_settings(DEBUG=True)
    def test_schema_200(self):
        r = self.client.get(reverse("api-schema"))
        self.assertEqual(r.status_code, 200)

    @override_settings(DEBUG=True)
    def test_docs_200(self):
        r = self.client.get(reverse("api-docs"))
        self.assertEqual(r.status_code, 200)
