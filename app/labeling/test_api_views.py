"""DRF API tests (labeling_api namespace)."""

import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from PIL import Image

from labeling.models import Annotation
from test_support.factories import (
    create_image_and_task,
    create_labeling_basics,
    create_project,
    ensure_membership,
    is_postgis,
)

from projects.models import ProjectMembership

User = get_user_model()


class LabelingAPIAuthTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("apio", "apio@t.local", "p")
        self.p = create_project(self.owner, title="APIP", access_level="private")
        self.schema, self.ds = create_labeling_basics(self.p)

    def _url(self, name, **kwargs):
        return reverse(f"labeling_api:{name}", kwargs=kwargs)

    def test_list_label_datasets_unauthenticated_rejected(self):
        c = APIClient()
        r = c.get(self._url("label_datasets_list", project_pk=self.p.pk))
        self.assertIn(r.status_code, (401, 403))

    def test_list_label_datasets_200(self):
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.get(self._url("label_datasets_list", project_pk=self.p.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_tasks_list_200(self):
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.get(self._url("tasks_list", project_pk=self.p.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_task_detail_404_member_not_assignee(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        ann_a = User.objects.create_user("tma", "tma@t.local", "p")
        ann_b = User.objects.create_user("tmb", "tmb@t.local", "p")
        ensure_membership(self.p, ann_a, ProjectMembership.Role.ANNOTATOR)
        ensure_membership(self.p, ann_b, ProjectMembership.Role.ANNOTATOR)
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        self.ds.assigned_users.set([ann_a])
        c = APIClient()
        c.force_authenticate(user=ann_b)
        r = c.get(self._url("task_detail", pk=task.pk))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_tasks_list_empty_for_non_assignee(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        ann_a = User.objects.create_user("tla", "tla@t.local", "p")
        ann_b = User.objects.create_user("tlb", "tlb@t.local", "p")
        ensure_membership(self.p, ann_a, ProjectMembership.Role.ANNOTATOR)
        ensure_membership(self.p, ann_b, ProjectMembership.Role.ANNOTATOR)
        create_image_and_task(self.p, self.schema, self.ds)
        self.ds.assigned_users.set([ann_a])
        c = APIClient()
        c.force_authenticate(user=ann_b)
        r = c.get(self._url("tasks_list", project_pk=self.p.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data.get("results", r.data)
        self.assertEqual(len(results), 0)

    def test_next_no_tasks_404(self):
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.get(self._url("tasks_next", project_pk=self.p.pk))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_200_owner(self):
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.post(
            self._url("project_export", project_pk=self.p.pk), {}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("zip", r.get("Content-Type", ""))

    def test_task_detail_404_stranger(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        _, task = out
        stranger = User.objects.create_user("aps", "aps@t.local", "p")
        c = APIClient()
        c.force_authenticate(user=stranger)
        r = c.get(self._url("task_detail", pk=task.pk))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_task_detail_200_member(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        _, task = out
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.get(self._url("task_detail", pk=task.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_draft_get_put(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        _, task = out
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.get(self._url("task_draft", pk=task.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        r2 = c.put(
            self._url("task_draft", pk=task.pk), {"result": []}, format="json"
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

    def test_annotations_get_post(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        _, task = out
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.post(
            self._url("task_annotations", pk=task.pk), {"result": []}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r2 = c.get(self._url("task_annotations", pk=task.pk))
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

    def test_dataset_import_masks_zip(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        self.assertIsNotNone(out)
        img, task = out
        img.refresh_from_db()
        w, h = img.width, img.height
        m = Image.new("L", (w, h), 0)
        px = m.load()
        for yy in range(h // 4, 3 * h // 4):
            for xx in range(w // 4, 3 * w // 4):
                px[xx, yy] = 1
        mb = io.BytesIO()
        m.save(mb, format="PNG")
        mb.seek(0)
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("s.png", mb.getvalue())
        zbuf.seek(0)
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.post(
            self._url(
                "dataset_import_masks",
                project_pk=self.p.pk,
                dataset_pk=self.ds.pk,
            ),
            {
                "file": SimpleUploadedFile(
                    "masks.zip", zbuf.read(), content_type="application/zip"
                ),
                "mapping": '{"1": "ex1"}',
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, getattr(r, "data", None))
        self.assertEqual(r.data.get("imported"), 1)
        self.assertGreaterEqual(Annotation.objects.filter(task=task).count(), 1)

    def test_annotation_status_patch_reviewer(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        _, task = out
        ann = Annotation.objects.create(
            task=task,
            completed_by=self.owner,
            result=[],
            status=Annotation.Status.SUBMITTED,
        )
        rev = User.objects.create_user("revx", "revx@t.local", "p")
        ensure_membership(self.p, rev, ProjectMembership.Role.REVIEWER)
        c = APIClient()
        c.force_authenticate(user=rev)
        r = c.patch(
            self._url("annotation_status", pk=ann.pk),
            {"status": Annotation.Status.APPROVED},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_lock_unlock(self):
        if not is_postgis():
            self.skipTest("PostGIS required")
        out = create_image_and_task(self.p, self.schema, self.ds)
        _, task = out
        c = APIClient()
        c.force_authenticate(user=self.owner)
        r = c.post(self._url("task_lock", pk=task.pk), {}, format="json")
        self.assertIn(r.status_code, (status.HTTP_200_OK, status.HTTP_409_CONFLICT))
        r2 = c.post(self._url("task_unlock", pk=task.pk), {}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
