"""URL/view tests for projects app."""

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from user.models import Role
from test_support.factories import create_project, ensure_membership

from .models import ProjectMembership

User = get_user_model()


class ProjectListViewTests(TestCase):
    def test_anonymous_redirects(self):
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 302)

    def test_authenticated_ok(self):
        u = User.objects.create_user("pl", "pl@t.local", "p")
        self.client.login(username="pl", password="p")
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_list.html")


class ProjectDetailViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("ow", "ow@t.local", "p")
        self.stranger = User.objects.create_user("st", "st@t.local", "p")
        self.priv = create_project(self.owner, title="Priv", access_level="private")
        self.pub = create_project(self.owner, title="Pub", access_level="public")

    def test_private_stranger_404(self):
        self.client.login(username="st", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.priv.pk})
        )
        self.assertEqual(r.status_code, 404)

    def test_private_owner_200(self):
        self.client.login(username="ow", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.priv.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_detail.html")

    def test_public_any_auth_200(self):
        self.client.login(username="st", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.pub.pk})
        )
        self.assertEqual(r.status_code, 200)


class ProjectCreateViewTests(TestCase):
    def test_non_editor_redirected(self):
        u = User.objects.create_user("ne", "ne@t.local", "p")
        self.client.login(username="ne", password="p")
        r = self.client.get(reverse("projects:project_create"))
        self.assertEqual(r.status_code, 302)

    def test_editor_200(self):
        u = User.objects.create_user("ed", "ed@t.local", "p")
        r = Role.objects.create(name="Editor", is_active=True, permissions=[])
        u.role = r
        u.save()
        self.client.login(username="ed", password="p")
        r = self.client.get(reverse("projects:project_create"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_form.html")


class ProjectEditDeleteTransferTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("ow2", "ow2@t.local", "p")
        self.other = User.objects.create_user("ot", "ot@t.local", "p")
        self.project = create_project(self.owner, title="P1", access_level="private")
        self.client.login(username="ow2", password="p")

    def test_edit_get_200(self):
        r = self.client.get(
            reverse("projects:project_edit", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_delete_get_200(self):
        r = self.client.get(
            reverse("projects:project_delete", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_transfer_get_200(self):
        r = self.client.get(
            reverse(
                "projects:project_transfer_ownership",
                kwargs={"pk": self.project.pk},
            )
        )
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_delete(self):
        self.client.login(username="ot", password="p")
        r = self.client.get(
            reverse("projects:project_delete", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 404)


class ProjectMembersViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("mow", "mow@t.local", "p")
        self.member = User.objects.create_user("mem", "mem@t.local", "p")
        self.p = create_project(self.owner, title="PM", access_level="private")
        ensure_membership(self.p, self.member, ProjectMembership.Role.ANNOTATOR)

    def test_owner_members_200(self):
        self.client.login(username="mow", password="p")
        r = self.client.get(
            reverse("projects:project_members", kwargs={"pk": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_members.html")

    def test_member_members_200(self):
        self.client.login(username="mem", password="p")
        r = self.client.get(
            reverse("projects:project_members", kwargs={"pk": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)


class ProjectMemberSubViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("aow", "aow@t.local", "p")
        self.to_remove = User.objects.create_user("tr", "tr@t.local", "p")
        self.p = create_project(self.owner, title="PR", access_level="private")
        ensure_membership(self.p, self.to_remove, ProjectMembership.Role.ANNOTATOR)

    def test_remove_post_302(self):
        self.client.login(username="aow", password="p")
        r = self.client.post(
            reverse(
                "projects:project_member_remove",
                kwargs={"pk": self.p.pk, "user_id": self.to_remove.id},
            )
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            ProjectMembership.objects.filter(
                project=self.p, user=self.to_remove
            ).exists()
        )

    def test_edit_role_get_200(self):
        self.client.login(username="aow", password="p")
        r = self.client.get(
            reverse(
                "projects:project_member_edit",
                kwargs={"pk": self.p.pk, "user_id": self.to_remove.id},
            )
        )
        self.assertEqual(r.status_code, 200)