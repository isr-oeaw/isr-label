from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Project, ProjectMembership

User = get_user_model()


class ProjectModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u1", email="u1@ex.com", password="p"
        )
        self.other = User.objects.create_user(
            username="u2", email="u2@ex.com", password="p"
        )

    def test_create_project_creates_admin_membership(self):
        p = Project.objects.create(
            title="T", description="D", owner=self.user, access_level="private"
        )
        m = p.memberships.get(user=self.user)
        self.assertEqual(m.role, ProjectMembership.Role.ADMIN)

    def test_is_accessible_by_member(self):
        p = Project.objects.create(
            title="T", description="D", owner=self.user, access_level="private"
        )
        assert p.is_accessible_by(self.user)
        ProjectMembership.objects.create(
            project=p, user=self.other, role=ProjectMembership.Role.ANNOTATOR
        )
        self.assertTrue(p.is_accessible_by(self.other))
        u3 = User.objects.create_user("u3", "u3@ex.com", "p")
        self.assertFalse(p.is_accessible_by(u3))


class ProjectViewSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u1", email="u1@ex.com", password="p", is_staff=True
        )
        self.client.login(username="u1", password="p")
        # Editor role: create is restricted to Editor/Admin site roles — use superuser for create
        self.admin = User.objects.create_superuser("su", "su@ex.com", "p")
        from user.models import Role
        r = Role.objects.create(name="Editor", is_active=True, permissions=[])
        self.user.role = r
        self.user.save()

    def test_project_list(self):
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 200)
