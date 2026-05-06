from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.db import connection
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from labeling.models import ImageAsset, LabelDataset, LabelSchema, Task
from projects.models import Project, ProjectMembership

User = get_user_model()


def is_postgis() -> bool:
    eng = (connection.settings_dict.get("ENGINE") or "").lower()
    return "postgis" in eng


def create_user(
    username="tuser", email="tuser@test.local", password="test-pass-12", **extra
):
    return User.objects.create_user(
        username=username, email=email, password=password, **extra
    )


def create_project(
    owner, title="TProj", description="Desc", access_level="private", **kwargs
):
    p = Project.objects.create(
        title=title,
        description=description,
        owner=owner,
        access_level=access_level,
        status=kwargs.pop("status", "active"),
        **kwargs,
    )
    return p


def ensure_membership(
    project: Project, user, role: str = ProjectMembership.Role.ANNOTATOR
):
    m, _ = ProjectMembership.objects.get_or_create(
        project=project, user=user, defaults={"role": role}
    )
    if m.role != role:
        m.role = role
        m.save()
    return m


def create_labeling_basics(project: Project):
    """LabelSchema + LabelDataset (no images)."""
    schema = LabelSchema.objects.create(
        project=project,
        version=1,
        config=LabelSchema.default_config(),
        is_active=True,
    )
    ds = LabelDataset.objects.create(
        project=project, name="ld1", description=""
    )
    return schema, ds


def create_image_and_task(
    project: Project,
    schema: LabelSchema,
    dataset: LabelDataset,
    inner_id: int = 1,
):
    """Requires PostGIS/GeoDjango (ImageAsset has PointField). Returns None if not PostGIS."""
    if not is_postgis():
        return None
    buf = BytesIO()
    Image.new("RGB", (8, 8), color=(40, 40, 200)).save(buf, format="PNG")
    buf.seek(0)
    f = SimpleUploadedFile("s.png", buf.getvalue(), content_type="image/png")
    img = ImageAsset.objects.create(dataset=dataset, file=f)
    task = Task.objects.create(
        project=project, image=img, schema=schema, inner_id=inner_id, overlap=1
    )
    return img, task
