"""URL/view tests for projects app."""

import unittest

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from user.models import Role
from test_support.factories import (
    create_image_and_task,
    create_labeling_basics,
    create_project,
    ensure_membership,
    is_postgis,
)

from .models import Project, ProjectMembership

User = get_user_model()


class ProjectListViewTests(TestCase):
    def test_anonymous_redirects(self):
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 302)

    def test_authenticated_member_sees_list(self):
        u = User.objects.create_user("pl", "pl@t.local", "p")
        owner = User.objects.create_user("own", "own@t.local", "p")
        p = create_project(owner, title="MemberProj", access_level="private")
        ensure_membership(p, u, ProjectMembership.Role.ANNOTATOR)
        self.client.login(username="pl", password="p")
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "MemberProj")

    def test_authenticated_non_staff_sees_public_projects_only(self):
        u = User.objects.create_user("pl2", "pl2@t.local", "p")
        owner = User.objects.create_user("own2", "own2@t.local", "p")
        create_project(owner, title="Secret", access_level="private")
        create_project(owner, title="Pubby", access_level="public")
        self.client.login(username="pl2", password="p")
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Pubby")
        self.assertNotContains(r, "Secret")

    def test_staff_ok(self):
        u = User.objects.create_user("stf", "stf@t.local", "p", is_staff=True)
        self.client.login(username="stf", password="p")
        r = self.client.get(reverse("projects:project_list"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_list.html")

    def test_superuser_ok(self):
        u = User.objects.create_superuser("supl", "supl@t.local", "p")
        self.client.login(username="supl", password="p")
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
        self.assertContains(r, "project-labeling-export")

    def test_public_any_auth_200(self):
        self.client.login(username="st", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.pub.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_private_annotator_no_edit_button(self):
        ann = User.objects.create_user("annpd", "annpd@t.local", "p")
        ensure_membership(self.priv, ann, ProjectMembership.Role.ANNOTATOR)
        self.client.login(username="annpd", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.priv.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(
            r, reverse("projects:project_edit", kwargs={"pk": self.priv.pk})
        )

    def test_private_owner_sees_edit_button(self):
        self.client.login(username="ow", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.priv.pk})
        )
        self.assertContains(
            r, reverse("projects:project_edit", kwargs={"pk": self.priv.pk})
        )


class ProjectLabelingExportDownloadTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("lexp", "lexp@t.local", "p")
        self.reviewer = User.objects.create_user("lrev", "lrev@t.local", "p")
        self.annotator = User.objects.create_user("lann", "lann@t.local", "p")
        User.objects.create_user("lst", "lst@t.local", "p")
        self.p = create_project(self.owner, title="LEX", access_level="private")
        ensure_membership(self.p, self.reviewer, ProjectMembership.Role.REVIEWER)
        ensure_membership(self.p, self.annotator, ProjectMembership.Role.ANNOTATOR)

    def _export_url(self):
        return reverse("labeling:project_export_download", kwargs={"project_id": self.p.pk})

    def test_export_owner_200_zip(self):
        self.client.login(username="lexp", password="p")
        r = self.client.get(self._export_url())
        self.assertEqual(r.status_code, 200)
        self.assertIn("zip", r.get("Content-Type", "").lower())

    def test_export_reviewer_200_zip(self):
        self.client.login(username="lrev", password="p")
        r = self.client.get(self._export_url())
        self.assertEqual(r.status_code, 200)
        self.assertIn("zip", r.get("Content-Type", "").lower())

    def test_export_annotator_403(self):
        self.client.login(username="lann", password="p")
        r = self.client.get(self._export_url())
        self.assertEqual(r.status_code, 403)

    def test_export_stranger_404(self):
        self.client.login(username="lst", password="p")
        r = self.client.get(self._export_url())
        self.assertEqual(r.status_code, 404)

    def test_detail_owner_shows_export_card(self):
        self.client.login(username="lexp", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "project-labeling-export")

    def test_detail_annotator_hides_export_card(self):
        self.client.login(username="lann", password="p")
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "project-labeling-export")


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

    def test_edit_page_shows_delete_link_for_owner(self):
        r = self.client.get(
            reverse("projects:project_edit", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r, reverse("projects:project_delete", kwargs={"pk": self.project.pk})
        )

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

    def test_annotator_cannot_open_edit(self):
        ann = User.objects.create_user("anned", "anned@t.local", "p")
        ensure_membership(
            self.project, ann, ProjectMembership.Role.ANNOTATOR
        )
        self.client.login(username="anned", password="p")
        r = self.client.get(
            reverse("projects:project_edit", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 404)

    def test_reviewer_cannot_open_edit(self):
        rev = User.objects.create_user("reved", "reved@t.local", "p")
        ensure_membership(self.project, rev, ProjectMembership.Role.REVIEWER)
        self.client.login(username="reved", password="p")
        r = self.client.get(
            reverse("projects:project_edit", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_open_edit_for_others_project(self):
        su = User.objects.create_superuser("sued", "sued@t.local", "p")
        self.client.login(username="sued", password="p")
        r = self.client.get(
            reverse("projects:project_edit", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_superuser_can_open_delete_for_others_project(self):
        su = User.objects.create_superuser("sudel", "sudel@t.local", "p")
        self.client.login(username="sudel", password="p")
        r = self.client.get(
            reverse("projects:project_delete", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(r.status_code, 200)

    @unittest.skipUnless(is_postgis(), "labeling tasks require PostGIS ImageAsset")
    def test_delete_post_succeeds_with_label_tasks(self):
        schema, ds = create_labeling_basics(self.project)
        pair = create_image_and_task(self.project, schema, ds)
        self.assertIsNotNone(pair)
        pk = self.project.pk
        r = self.client.post(reverse("projects:project_delete", kwargs={"pk": pk}))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=pk).exists())


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