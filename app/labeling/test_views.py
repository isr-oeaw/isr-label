"""HTML view tests for labeling app."""

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from test_support.factories import (
    create_image_and_task,
    create_labeling_basics,
    create_project,
    ensure_membership,
    is_postgis,
)

from projects.models import ProjectMembership

User = get_user_model()


class LabelingAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("low", "low@t.local", "p")
        self.stranger = User.objects.create_user("ls", "ls@t.local", "p")
        self.p = create_project(self.owner, title="LP", access_level="private")

    def test_dashboard_stranger_404(self):
        self.client.login(username="ls", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 404)

    def test_dashboard_owner_200(self):
        self.client.login(username="low", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/project_dashboard.html")


class LabelingDatasetViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("lown", "lown@t.local", "p")
        self.p = create_project(self.owner, title="LD", access_level="private")
        create_labeling_basics(self.p)
        self.client.login(username="lown", password="p")

    def test_dataset_list_200(self):
        r = self.client.get(
            reverse("labeling:dataset_list", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/dataset_list.html")

    def test_dataset_create_get_200(self):
        r = self.client.get(
            reverse("labeling:dataset_create", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)


class LabelingGeoAndTaskViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("go", "go@t.local", "p")
        self.p = create_project(self.owner, title="LG", access_level="private")
        self.schema, self.ds = create_labeling_basics(self.p)
        self.client.login(username="go", password="p")

    def test_map_200_or_skip(self):
        if not is_postgis():
            self.skipTest("PostGIS required for map geojson pipeline")
        r = self.client.get(
            reverse("labeling:map", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_schema_edit_get_200(self):
        r = self.client.get(
            reverse("labeling:schema", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_next_redirects(self):
        r = self.client.get(
            reverse("labeling:next", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 302)

    def test_task_view_200_with_task(self):
        if not is_postgis():
            self.skipTest("PostGIS required for ImageAsset/Task")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        r = self.client.get(
            reverse(
                "labeling:task",
                kwargs={"project_id": self.p.pk, "task_id": task.pk},
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/task.html")


class ReviewListViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("rv", "rv@t.local", "p")
        self.rev = User.objects.create_user("revu", "revu@t.local", "p")
        self.p = create_project(self.owner, title="RV", access_level="private")
        ensure_membership(self.p, self.rev, ProjectMembership.Role.REVIEWER)

    def test_reviewer_200(self):
        self.client.login(username="revu", password="p")
        r = self.client.get(
            reverse("labeling:review", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)

    def test_annotator_404(self):
        ann = User.objects.create_user("annv", "annv@t.local", "p")
        ensure_membership(self.p, ann, ProjectMembership.Role.ANNOTATOR)
        self.client.login(username="annv", password="p")
        r = self.client.get(
            reverse("labeling:review", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 404)
