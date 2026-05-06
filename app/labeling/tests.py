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
        project=p, user=u1, role=ProjectMembership.Role.ADMIN
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
    ProjectMembership.objects.create(
        project=p, user=u, role=ProjectMembership.Role.ADMIN
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
        version=1,
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
