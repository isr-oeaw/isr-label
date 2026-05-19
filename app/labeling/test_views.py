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
        self.assertContains(r, "labeling-my-tasks")


class LabelingDatasetViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("lown", "lown@t.local", "p")
        self.p = create_project(self.owner, title="LD", access_level="private")
        self.schema, self.ds = create_labeling_basics(self.p)
        self.client.login(username="lown", password="p")

    def test_project_detail_shows_label_datasets_section(self):
        r = self.client.get(
            reverse("projects:project_detail", kwargs={"pk": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "projects/project_detail.html")

    def test_legacy_label_datasets_list_url_404(self):
        r = self.client.get(f"/labeling/projects/{self.p.pk}/datasets/")
        self.assertEqual(r.status_code, 404)

    def test_create_label_tasks_post_creates_tasks(self):
        if not is_postgis():
            self.skipTest("PostGIS required for ImageAsset")
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from labeling.models import ImageAsset, Task

        buf = BytesIO()
        Image.new("RGB", (4, 4), color=(1, 2, 3)).save(buf, format="PNG")
        buf.seek(0)
        f = SimpleUploadedFile("x.png", buf.getvalue(), content_type="image/png")
        ImageAsset.objects.create(dataset=self.ds, file=f)
        self.assertEqual(Task.objects.filter(project=self.p).count(), 0)
        r = self.client.post(
            reverse(
                "labeling:dataset_create_tasks",
                kwargs={"project_id": self.p.pk, "dataset_id": self.ds.pk},
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Task.objects.filter(project=self.p).count(), 1)

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

    def test_dashboard_owner_200(self):
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/project_dashboard.html")
        self.assertContains(r, "labeling-my-tasks")

    def test_schema_list_200(self):
        r = self.client.get(
            reverse("labeling:schema_list", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/schema_list.html")

    def test_schema_legacy_redirects_to_list(self):
        r = self.client.get(
            reverse("labeling:schema", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            r.url,
            reverse("labeling:schema_list", kwargs={"project_id": self.p.pk}),
        )

    def test_schema_edit_get_200(self):
        r = self.client.get(
            reverse(
                "labeling:schema_edit",
                kwargs={"project_id": self.p.pk},
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "labeling/schema_editor.html")

    def test_apply_template_post_updates_setup(self):
        self.assertEqual(self.p.label_schemata.count(), 1)
        schema_pk = self.schema.pk
        r = self.client.post(
            reverse(
                "labeling:schema_apply_template",
                kwargs={"project_id": self.p.pk},
            ),
            {"slug": "bounding_boxes"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.p.label_schemata.count(), 1)
        self.schema.refresh_from_db()
        self.assertEqual(self.schema.pk, schema_pk)
        self.assertTrue(self.schema.is_active)
        self.assertEqual(self.schema.config.get("tools"), ["rect"])
        self.assertEqual(
            self.schema.config.get("_meta", {}).get("template_slug"), "bounding_boxes"
        )

    def test_apply_template_forbidden_for_annotator(self):
        ann = User.objects.create_user("annb", "annb@t.local", "p")
        ensure_membership(self.p, ann, ProjectMembership.Role.ANNOTATOR)
        self.client.login(username="annb", password="p")
        r = self.client.post(
            reverse(
                "labeling:schema_apply_template",
                kwargs={"project_id": self.p.pk},
            ),
            {"slug": "bounding_boxes"},
        )
        self.assertEqual(r.status_code, 403)

    def test_schema_edit_guided_post_updates_config(self):
        r = self.client.post(
            reverse(
                "labeling:schema_edit",
                kwargs={"project_id": self.p.pk},
            ),
            {
                "tools": ["rect"],
                "allow_empty": "on",
                "multi_label": "",
                "use_advanced_json": "",
                "config_text": "{}",
                "is_active": "on",
                "labels-TOTAL_FORMS": "1",
                "labels-INITIAL_FORMS": "0",
                "labels-MIN_NUM_FORMS": "0",
                "labels-MAX_NUM_FORMS": "1000",
                "labels-0-label_id": "x1",
                "labels-0-name": "Alpha",
                "labels-0-color": "#ff0000",
                "labels-0-hotkey": "9",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.schema.refresh_from_db()
        self.assertEqual(self.schema.config.get("tools"), ["rect"])
        labs = self.schema.config.get("labels") or []
        self.assertEqual(len(labs), 1)
        self.assertEqual(labs[0].get("name"), "Alpha")
        self.assertEqual(labs[0].get("id"), "x1")
        self.assertFalse(
            bool((self.schema.config.get("_meta") or {}).get("mask_import_enabled"))
        )

    def test_schema_edit_saves_instructions(self):
        r = self.client.post(
            reverse(
                "labeling:schema_edit",
                kwargs={"project_id": self.p.pk},
            ),
            {
                "tools": ["rect"],
                "allow_empty": "on",
                "multi_label": "",
                "instructions": "<p>Only label <strong>vehicles</strong>.</p>",
                "use_advanced_json": "",
                "config_text": "{}",
                "is_active": "on",
                "labels-TOTAL_FORMS": "1",
                "labels-INITIAL_FORMS": "0",
                "labels-MIN_NUM_FORMS": "0",
                "labels-MAX_NUM_FORMS": "1000",
                "labels-0-label_id": "x1",
                "labels-0-name": "Alpha",
                "labels-0-color": "#ff0000",
                "labels-0-hotkey": "9",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.schema.refresh_from_db()
        self.assertIn("vehicles", self.schema.config.get("instructions", ""))
        self.assertNotIn("<script>", self.schema.config.get("instructions", ""))

    def test_task_view_shows_instructions_modal(self):
        if not is_postgis():
            self.skipTest("PostGIS required for task with image")
        from test_support.factories import create_image_and_task

        self.schema.config = {
            **(self.schema.config or {}),
            "instructions": "<p>Task help text</p>",
        }
        self.schema.save()
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        r = self.client.get(
            reverse(
                "labeling:task",
                kwargs={"project_id": self.p.pk, "task_id": task.id},
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Task help text")
        self.assertContains(r, "labelingInstructionsModal")

    def test_schema_edit_mask_import_flag_persists(self):
        r = self.client.post(
            reverse(
                "labeling:schema_edit",
                kwargs={"project_id": self.p.pk},
            ),
            {
                "tools": ["polygon"],
                "allow_empty": "on",
                "multi_label": "",
                "mask_import_enabled": "on",
                "use_advanced_json": "",
                "config_text": "{}",
                "is_active": "on",
                "labels-TOTAL_FORMS": "1",
                "labels-INITIAL_FORMS": "0",
                "labels-MIN_NUM_FORMS": "0",
                "labels-MAX_NUM_FORMS": "1000",
                "labels-0-label_id": "x1",
                "labels-0-name": "Alpha",
                "labels-0-color": "#ff0000",
                "labels-0-hotkey": "9",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.schema.refresh_from_db()
        self.assertTrue((self.schema.config.get("_meta") or {}).get("mask_import_enabled"))

    def test_schema_list_includes_template_section(self):
        r = self.client.get(
            reverse("labeling:schema_list", kwargs={"project_id": self.p.pk})
        )
        self.assertContains(r, "bounding_boxes", status_code=200)

    def test_schema_toggle_labeling_post(self):
        self.assertTrue(self.schema.selected_for_labeling)
        r = self.client.post(
            reverse(
                "labeling:schema_toggle_labeling",
                kwargs={"project_id": self.p.pk, "schema_pk": self.schema.pk},
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.schema.refresh_from_db()
        self.assertFalse(self.schema.selected_for_labeling)

    def test_next_redirects(self):
        r = self.client.get(
            reverse("labeling:next", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 302)

    def test_global_next_redirects_home_when_no_tasks(self):
        r = self.client.get(reverse("labeling:next_global"))
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)

    def test_global_next_redirects_to_task_when_available(self):
        if not is_postgis():
            self.skipTest("PostGIS required for ImageAsset/Task")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        r = self.client.get(reverse("labeling:next_global"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"/labeling/projects/{self.p.pk}/tasks/{task.pk}/", r.url)

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
        self.assertContains(r, "label-stage-wrapper")
        self.assertContains(r, "labeling-sidebar")


class DatasetAssigneeVisibilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("da_o", "da_o@t.local", "p")
        self.ann_a = User.objects.create_user("da_a", "da_a@t.local", "p")
        self.ann_b = User.objects.create_user("da_b", "da_b@t.local", "p")
        self.p = create_project(self.owner, title="DAV", access_level="private")
        self.schema, self.ds = create_labeling_basics(self.p)
        ensure_membership(self.p, self.ann_a, ProjectMembership.Role.ANNOTATOR)
        ensure_membership(self.p, self.ann_b, ProjectMembership.Role.ANNOTATOR)

    def test_restricted_dataset_hides_task_from_non_assignee(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        self.ds.assigned_users.set([self.ann_a])
        self.client.login(username="da_b", password="p")
        r = self.client.get(
            reverse(
                "labeling:task",
                kwargs={"project_id": self.p.pk, "task_id": task.pk},
            )
        )
        self.assertEqual(r.status_code, 404)

    def test_assignee_sees_task(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        self.ds.assigned_users.set([self.ann_a])
        self.client.login(username="da_a", password="p")
        r = self.client.get(
            reverse(
                "labeling:task",
                kwargs={"project_id": self.p.pk, "task_id": task.pk},
            )
        )
        self.assertEqual(r.status_code, 200)

    def test_owner_dashboard_shows_team_tasks_section_when_assignees_exclude_owner(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        self.ds.assigned_users.set([self.ann_a])
        self.client.login(username="da_o", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "labeling-my-tasks")
        self.assertContains(r, "labeling-team-tasks")

    def test_annotator_dashboard_hides_team_tasks_section(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        self.ds.assigned_users.set([self.ann_a])
        self.client.login(username="da_a", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "labeling-my-tasks")
        self.assertNotContains(r, "labeling-team-tasks")

    def test_project_admin_dashboard_hides_team_tasks_section(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        admin_u = User.objects.create_user("da_adm", "da_adm@t.local", "p")
        ensure_membership(self.p, admin_u, ProjectMembership.Role.ADMIN)
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        self.ds.assigned_users.set([self.ann_a])
        self.client.login(username="da_adm", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "labeling-my-tasks")
        self.assertNotContains(r, "labeling-team-tasks")

    def test_owner_dashboard_hides_team_tasks_when_all_tasks_in_assignee_slice(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        self.client.login(username="da_o", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "labeling-my-tasks")
        self.assertNotContains(r, "labeling-team-tasks")

    def test_owner_dashboard_shows_team_progress(self):
        self.client.login(username="da_o", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "labeling-team-progress")

    def test_annotator_dashboard_hides_team_progress(self):
        self.client.login(username="da_a", password="p")
        r = self.client.get(
            reverse("labeling:dashboard", kwargs={"project_id": self.p.pk})
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "labeling-team-progress")

    def test_dataset_assignees_page_200_admin(self):
        self.client.login(username="da_o", password="p")
        r = self.client.get(
            reverse(
                "labeling:dataset_assignees",
                kwargs={"project_id": self.p.pk, "dataset_id": self.ds.pk},
            )
        )
        self.assertEqual(r.status_code, 200)


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
