# Permissions

## Roles (`ProjectMembership.Role`)

| Role | View project | Label | Review | Manage members & schema | Export |
|------|-------------|--------|--------|-------------------------|--------|
| admin | yes | yes | yes | yes | yes |
| reviewer | yes | optional | yes | no | yes |
| annotator | yes | yes | no | no | no* |
| viewer | yes | no | no | no | no* |

*MVP: export may be admin/reviewer only; configurable in `labeling` views.

## Project owner

- `Project.owner` always has **admin** effective rights.
- `ensure_owner_membership()` syncs a `ProjectMembership` row with `role=admin` for `owner` on `Project.save` when needed.

## DRF

- **`is_project_member_factory(*roles)`** in `labeling/permissions.py` returns a `BasePermission` subclass that enforces
  `ProjectMembership.Role` (e.g. `is_project_member_factory('admin', 'annotator')` on a view as `permission_classes = [IsAuthenticated, …]`).
- **`IsProjectLabelingMember`**: any project member, owner, or public access per object.
- `Project.owner` is treated as admin in `user_project_role()`; superuser always passes factory checks.

## Public / restricted / private

- Reuses `Project.is_accessible_by` for listing and detail: public projects visible to all authenticated users; restricted requires `can_manage_projects`; private requires membership/owner or superuser.

After introducing memberships, "collaborator" is replaced: any user in `ProjectMembership` is a member. Listing projects for a user can filter by: owner, member, or public.

## Labeling object permissions

- **Task lock**: only the locking user (or admin) can release early.
- **Annotation**: user can only edit their own draft; submitted annotations immutable except reviewer workflow.

## Review workflow (Phase 4)

- `Annotation.status`: `submitted` → `approved` / `rejected` / `needs_revision` (by reviewer or admin).
- Only reviewers+ can change status to approved/rejected.
