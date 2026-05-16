import pytest
from django.contrib.auth import get_user_model
from projects.models import Project, ProjectMembership

User = get_user_model()


@pytest.mark.django_db
def test_project_membership_unique():
    u1 = User.objects.create_user("u1", "u1@test.local", "pass-1234")
    u2 = User.objects.create_user("u2", "u2@test.local", "pass-1234")
    p = Project.objects.create(
        title="P", description="D", owner=u1, status="active", access_level="private"
    )
    ProjectMembership.objects.create(
        project=p, user=u2, role=ProjectMembership.Role.ANNOTATOR
    )
    assert p.memberships.count() == 2
    assert p.is_accessible_by(u2)


def test_label_schema_default_config():
    from labeling.models import LabelSchema

    c = LabelSchema.default_config()
    assert "labels" in c
    assert "tools" in c


def test_cv_setup_templates_build_config():
    from labeling.cv_setup_templates import build_config_from_template, get_cv_template

    c = build_config_from_template("bounding_boxes")
    assert c is not None
    assert c["tools"] == ["rect"]
    assert c["_meta"]["template_slug"] == "bounding_boxes"
    assert get_cv_template("not_a_real_slug") is None
    assert build_config_from_template("not_a_real_slug") is None
    t = get_cv_template("bounding_boxes")
    assert t is not None
    assert t.category == "detection"


def test_sanitize_labeling_instructions():
    from labeling.services.rich_text import sanitize_labeling_instructions

    assert sanitize_labeling_instructions("") == ""
    assert sanitize_labeling_instructions("   ") == ""
    out = sanitize_labeling_instructions('<script>x</script><p>Hi</p>')
    assert "<script>" not in out.lower()
    assert "Hi</p>" in out or "hi</p>" in out.lower()


def test_mask_array_to_polygon_regions():
    import numpy as np

    from labeling.services.mask_to_polygons import mask_array_to_polygon_regions

    arr = np.zeros((20, 30), dtype=np.uint32)
    arr[5:15, 10:25] = 1
    regions = mask_array_to_polygon_regions(
        arr, 30, 20, {1: "car"}, background_values=frozenset({0})
    )
    assert len(regions) >= 1
    assert regions[0]["type"] == "polygon"
    assert regions[0]["label_id"] == "car"
    assert len(regions[0]["points"]) >= 3


def test_build_coco_polygon_has_segmentation():
    from unittest.mock import MagicMock

    from labeling.services.exporters.coco import build_coco

    img = MagicMock()
    img.id = 7
    img.width = 100
    img.height = 80
    img.file.name = "folder/z.jpg"
    task = MagicMock()
    task.image = img
    ann = MagicMock()
    ann.was_cancelled = False
    ann.result = [
        {
            "type": "polygon",
            "label_id": "c1",
            "points": [[0.1, 0.1], [0.2, 0.1], [0.15, 0.25]],
            "_source": "mask_import",
        }
    ]
    d = build_coco(42, [(task, [ann])])
    assert len(d["annotations"]) == 1
    a0 = d["annotations"][0]
    assert "segmentation" in a0
    assert len(a0["segmentation"][0]) >= 6
    assert a0["bbox"][0] <= a0["segmentation"][0][0]


@pytest.mark.django_db
def test_toy_project_three_images_creates_tasks():
    """Labeling pipeline: 3 ImageAssets in one dataset, each with a Task (PostGIS DB)."""
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection
    from PIL import Image

    if "postgis" not in (connection.settings_dict.get("ENGINE") or ""):
        pytest.skip("PostGIS / GeoDjango required")

    u = User.objects.create_user("im", "im@test.local", "pass-1234")
    p = Project.objects.create(
        title="ImgP", description="D", owner=u, access_level="private"
    )
    from labeling.models import (
        ImageAsset,
        LabelDataset,
        LabelSchema,
        Task,
    )

    ds = LabelDataset.objects.create(project=p, name="ds1", description="")
    schema = LabelSchema.objects.create(
        project=p,
        config=LabelSchema.default_config(),
        is_active=True,
    )
    for i in range(3):
        buf = BytesIO()
        Image.new("RGB", (12, 12), color=(i * 30, 10, 10)).save(buf, format="PNG")
        buf.seek(0)
        f = SimpleUploadedFile(
            f"shot{i}.png", buf.getvalue(), content_type="image/png"
        )
        ImageAsset.objects.create(dataset=ds, file=f)
    for i, img in enumerate(
        ImageAsset.objects.filter(dataset=ds).order_by("id"), start=1
    ):
        Task.objects.create(
            project=p, image=img, schema=schema, inner_id=i, overlap=1
        )
    assert ImageAsset.objects.filter(dataset=ds).count() == 3
    assert Task.objects.filter(project=p).count() == 3
