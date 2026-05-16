"""Next-task selection, locks."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Optional

from django.db.models import Exists, OuterRef
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from projects.models import Project
    from labeling.models import Task

log = logging.getLogger(__name__)

LOCK_TTL = datetime.timedelta(minutes=30)


def _expire_stale_locks() -> int:
    from labeling.models import TaskLock

    n, _ = TaskLock.objects.filter(expire_at__lt=timezone.now()).delete()
    return n


def get_next_task_for(user: "AbstractUser", project: "Project") -> Optional["Task"]:
    """
    Return next label task for the user, or None.
    Excludes: tasks the user already annotated (non-cancelled), tasks locked by others, completed tasks.
    """
    from labeling.models import Annotation, Task, TaskLock

    if not user or not user.is_authenticated:
        return None

    _expire_stale_locks()

    already_annotated = Annotation.objects.filter(
        task=OuterRef("pk"),
        completed_by=user,
        was_cancelled=False,
    )
    other_lock = TaskLock.objects.filter(
        task=OuterRef("pk"),
        expire_at__gte=timezone.now(),
    ).exclude(user=user)

    qs = (
        Task.objects.filter(project=project, is_labeled=False)
        .select_related("image", "schema", "image__dataset")
        .annotate(
            has_mine=Exists(already_annotated),
        )
        .filter(has_mine=False)
        .annotate(locked_by_other=Exists(other_lock))
        .filter(locked_by_other=False)
    )
    from labeling.services.task_visibility import filter_personal_label_tasks

    qs = filter_personal_label_tasks(project, user, qs).order_by("inner_id", "id")

    return qs.first()


def get_next_task_globally(user: "AbstractUser"):
    """
    Next labelable task across projects reachable from the home dashboard list
    (same project filter as the project list for non-superusers).
    Returns (project, task) or None.
    """
    from django.db.models import Q

    from projects.models import Project

    if not user or not user.is_authenticated:
        return None

    _expire_stale_locks()

    qs = Project.objects.select_related("owner").order_by("-updated_at")
    if not user.is_superuser:
        qs = qs.filter(
            Q(owner=user) | Q(memberships__user=user) | Q(access_level="public")
        ).distinct()

    for p in qs:
        if not p.is_accessible_by(user):
            continue
        t = get_next_task_for(user, p)
        if t:
            return p, t
    return None


def acquire_lock(user: "AbstractUser", task: "Task") -> tuple[bool, str]:
    from labeling.models import TaskLock

    _expire_stale_locks()
    other = task.locks.filter(expire_at__gte=timezone.now()).exclude(user=user).first()
    if other:
        return False, "locked_by_other"
    at = timezone.now() + LOCK_TTL
    TaskLock.objects.update_or_create(
        task=task,
        user=user,
        defaults={"expire_at": at},
    )
    return True, "ok"


def release_lock(user: "AbstractUser", task: "Task") -> None:
    from labeling.models import TaskLock

    TaskLock.objects.filter(task=task, user=user).delete()


def get_next_task_inner_id(project: "Project") -> int:
    from django.db.models import Max

    from labeling.models import Task

    m = Task.objects.filter(project=project).aggregate(Max("inner_id"))["inner_id__max"]
    return (m or 0) + 1


def ensure_tasks_for_dataset(dataset) -> int:
    """Create a Task for each image in the dataset that has no task. Returns number of tasks created."""
    from django.db.models import Count

    from labeling.models import ImageAsset, LabelSchema, Task

    p = dataset.project
    schema = p.label_schemata.filter(is_active=True).order_by('-id').first()
    if not schema:
        schema = LabelSchema.objects.create(
            project=p,
            config=LabelSchema.default_config(),
            is_active=True,
            selected_for_labeling=True,
        )

    images = (
        ImageAsset.objects.filter(dataset=dataset)
        .annotate(_tc=Count('tasks'))
        .filter(_tc=0)
    )
    img_list = list(images)
    if not img_list:
        return 0

    start_inner = get_next_task_inner_id(p)
    for offset, img in enumerate(img_list):
        Task.objects.create(
            project=p,
            image=img,
            schema=schema,
            inner_id=start_inner + offset,
            overlap=1,
        )
    return len(img_list)
