"""Who may see which label tasks (dataset assignees, owner/admin override)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from labeling.models import LabelDataset, Task
    from projects.models import Project


def _is_project_admin(project: 'Project', user: 'AbstractUser') -> bool:
    from projects.models import ProjectMembership

    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.id == project.owner_id:
        return True
    m = project.get_membership(user)
    return m is not None and m.role == ProjectMembership.Role.ADMIN


def user_sees_all_project_tasks(project: 'Project', user: 'AbstractUser') -> bool:
    return _is_project_admin(project, user)


def user_has_dataset_access(user: 'AbstractUser', dataset: 'LabelDataset') -> bool:
    if not dataset.assigned_users.exists() and not dataset.assigned_groups.exists():
        return True
    if dataset.assigned_users.filter(pk=user.pk).exists():
        return True
    user_gids = user.groups.values_list('id', flat=True)
    if dataset.assigned_groups.filter(id__in=user_gids).exists():
        return True
    return False


def dataset_ids_accessible_to_user(project: 'Project', user: 'AbstractUser') -> Optional[set[int]]:
    """
    Return dataset PK set the user may label, or None if all project datasets apply
    (owner/admin: no filter).
    """
    from labeling.models import LabelDataset

    if user_sees_all_project_tasks(project, user):
        return None

    base = LabelDataset.objects.filter(project=project).annotate(
        nu=Count('assigned_users', distinct=True),
        ng=Count('assigned_groups', distinct=True),
    )
    open_ids = set(base.filter(nu=0, ng=0).values_list('id', flat=True))

    restricted = base.filter(Q(nu__gt=0) | Q(ng__gt=0))
    user_gids = list(user.groups.values_list('id', flat=True))
    user_q = Q(assigned_users=user)
    group_q = Q(assigned_groups__in=user_gids) if user_gids else Q(pk__in=[])
    restricted_ok = set(restricted.filter(user_q | group_q).values_list('id', flat=True).distinct())

    return open_ids | restricted_ok


def dataset_ids_by_assignee_rules_only(project: 'Project', user: 'AbstractUser') -> set[int]:
    """
    Dataset PKs the user may label using only assignee rules (open datasets + restricted
    where the user/group matches). Ignores owner/admin \"see all\" bypass.
    """
    from labeling.models import LabelDataset

    base = LabelDataset.objects.filter(project=project).annotate(
        nu=Count('assigned_users', distinct=True),
        ng=Count('assigned_groups', distinct=True),
    )
    open_ids = set(base.filter(nu=0, ng=0).values_list('id', flat=True))

    restricted = base.filter(Q(nu__gt=0) | Q(ng__gt=0))
    user_gids = list(user.groups.values_list('id', flat=True))
    user_q = Q(assigned_users=user)
    group_q = Q(assigned_groups__in=user_gids) if user_gids else Q(pk__in=[])
    restricted_ok = set(restricted.filter(user_q | group_q).values_list('id', flat=True).distinct())

    return open_ids | restricted_ok


def filter_tasks_assignee_slice(
    project: 'Project',
    user: 'AbstractUser',
    queryset: QuerySet['Task'],
) -> QuerySet['Task']:
    ids = dataset_ids_by_assignee_rules_only(project, user)
    if not ids:
        return queryset.none()
    return queryset.filter(image__dataset_id__in=ids)


def filter_tasks_for_user(
    project: 'Project',
    user: 'AbstractUser',
    queryset: QuerySet['Task'],
) -> QuerySet['Task']:
    ids = dataset_ids_accessible_to_user(project, user)
    if ids is None:
        return queryset
    if not ids:
        return queryset.none()
    return queryset.filter(image__dataset_id__in=ids)


def filter_personal_label_tasks(
    project: 'Project',
    user: 'AbstractUser',
    queryset: QuerySet['Task'],
) -> QuerySet['Task']:
    """
    Tasks counted as "mine" on the labeling dashboard: project owners use the
    assignee slice only; everyone else uses dataset visibility rules.
    """
    if user.id == project.owner_id:
        return filter_tasks_assignee_slice(project, user, queryset)
    return filter_tasks_for_user(project, user, queryset)


def user_can_access_task(user: 'AbstractUser', task: 'Task') -> bool:
    project = task.project
    if user_sees_all_project_tasks(project, user):
        return True
    ids = dataset_ids_accessible_to_user(project, user)
    if ids is None:
        return True
    return bool(task.image_id) and task.image.dataset_id in ids


def pending_visible_tasks_count(project: 'Project', user: 'AbstractUser') -> int:
    """Tasks the user may see, incomplete, not yet annotated by them (non-cancelled)."""
    from labeling.models import Annotation, Task, TaskLock
    from labeling.services import queue as queue_svc

    queue_svc._expire_stale_locks()

    already = Annotation.objects.filter(
        task=OuterRef('pk'),
        completed_by=user,
        was_cancelled=False,
    )
    other_lock = TaskLock.objects.filter(
        task=OuterRef('pk'),
        expire_at__gte=timezone.now(),
    ).exclude(user=user)

    qs = Task.objects.filter(project=project, is_labeled=False)
    qs = filter_tasks_for_user(project, user, qs)
    return (
        qs.annotate(has_mine=Exists(already))
        .filter(has_mine=False)
        .annotate(locked_by_other=Exists(other_lock))
        .filter(locked_by_other=False)
        .count()
    )


def submitted_annotations_count(project: 'Project', user: 'AbstractUser') -> int:
    from labeling.models import Annotation

    return Annotation.objects.filter(
        task__project=project,
        completed_by=user,
        was_cancelled=False,
    ).count()
