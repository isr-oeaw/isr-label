"""DRF and helper permission checks for labeling."""

from __future__ import annotations

from rest_framework import permissions

from projects.models import Project, ProjectMembership


def user_project_role(user, project: Project) -> str | None:
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ProjectMembership.Role.ADMIN
    if user.id == project.owner_id:
        return ProjectMembership.Role.ADMIN
    m = project.get_membership(user)
    return m.role if m else None


def can_label(user, project: Project) -> bool:
    r = user_project_role(user, project)
    return r in (
        ProjectMembership.Role.ADMIN,
        ProjectMembership.Role.REVIEWER,
        ProjectMembership.Role.ANNOTATOR,
    )


def can_review(user, project: Project) -> bool:
    r = user_project_role(user, project)
    return r in (ProjectMembership.Role.ADMIN, ProjectMembership.Role.REVIEWER)


def can_export(user, project: Project) -> bool:
    r = user_project_role(user, project)
    return r in (ProjectMembership.Role.ADMIN, ProjectMembership.Role.REVIEWER)


def _project_for_obj(obj) -> Project | None:
    if isinstance(obj, Project):
        return obj
    p = getattr(obj, 'project', None)
    if p is not None:
        return p
    t = getattr(obj, 'task', None)
    if t is not None and hasattr(t, 'project'):
        return t.project
    return None


def is_project_member_factory(*allowed_roles: str, allow_superuser: bool = True):
    """
    Build a DRF permission class restricted to the given ProjectMembership.Role values.

    Example::

        permission_classes = [
            IsAuthenticated,
            is_project_member_factory(
                ProjectMembership.Role.ADMIN,
                ProjectMembership.Role.REVIEWER,
            ),
        ]
    """
    roles = frozenset(allowed_roles) if allowed_roles else frozenset(
        (
            ProjectMembership.Role.ADMIN,
            ProjectMembership.Role.REVIEWER,
            ProjectMembership.Role.ANNOTATOR,
            ProjectMembership.Role.VIEWER,
        )
    )

    class IsProjectMember(permissions.BasePermission):
        def has_object_permission(self, request, view, obj):
            if not request.user or not request.user.is_authenticated:
                return False
            project = _project_for_obj(obj)
            if not project or not project.is_accessible_by(request.user):
                return False
            if allow_superuser and request.user.is_superuser:
                return True
            r = user_project_role(request.user, project)
            if r is None:
                return project.access_level == 'public' and (
                    ProjectMembership.Role.VIEWER in roles
                )
            return r in roles

    return IsProjectMember


class IsProjectLabelingMember(permissions.BasePermission):
    """User must be able to access the project (member, owner, or public read)."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        project = _project_for_obj(obj)
        if not project or not project.is_accessible_by(request.user):
            return False
        if user_project_role(request.user, project) is not None:
            return True
        if project.access_level == 'public':
            return True
        return False
