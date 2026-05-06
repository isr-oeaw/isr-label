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
        .order_by("inner_id", "id")
    )

    return qs.first()


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
    from labeling.models import Task
    from django.db.models import Max

    m = Task.objects.filter(project=project).aggregate(Max("inner_id"))["inner_id__max"]
    return (m or 0) + 1
