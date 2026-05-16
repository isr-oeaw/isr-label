# Data model

## ERD (conceptual)

```
Project (1) ----< Dataset (1) ----< ImageAsset
   |                    \
   |                     `----< Task >---- ImageAsset
   |                                    \
ProjectMembership                    LabelSchema
                                     Annotation, AnnotationDraft, TaskLock
```

## `ProjectMembership`

- `project` FK, `user` FK, `role` in `{admin, reviewer, annotator, viewer}`.
- `unique_together` (project, user).
- **Owner** is still `Project.owner` (FK); owner is mirrored as membership with `admin` on save/migration.

## `labeling.LabelDataset`

- FK to `Project`, unique `(project, name)`.
- **`assigned_users`** / **`assigned_groups`** (M2M): optional **restrictions** on who may see labeling tasks for images in this dataset (`django.contrib.auth` users and `auth.Group`).
  - If **both** are empty, any project member who can label may work on tasks from this dataset (existing behavior).
  - If either is non-empty, only users listed directly **or** in an assigned group may see those tasks in the queue, labeling dashboard, and task URLs (unless they are project owner or project Admin, who see everything in the project).
- Assignees are managed in the **Manage assignees** UI (project dataset card) or via the dataset API (`assigned_user_ids` / `assigned_group_ids` on create/update).

## `labeling.LabelSchema`

At most **one** row per project (`UniqueConstraint` on `project`). Stores `config` (JSON), `is_active`, and `selected_for_labeling`. Applying a template **replaces** `config` on that row.

## `labeling.LabelSchema.config` (JSON)

Optional lineage: `config._meta.template_slug` records which **labeling setup** template was last applied from `labeling.cv_setup_templates`. `config._meta.mask_import_enabled` (boolean) records that admins opted in to mask/segmentation PNG import.

Optional **annotator instructions**: `config.instructions` (string, HTML subset) is edited in the labeling setup UI, sanitized on save (`bleach` allowlist), and shown in a modal on the task labeling page.

Example:

```json
{
  "tools": ["classification", "rect", "polygon", "point"],
  "labels": [
    {"id": "obj1", "name": "Object", "color": "#e74c3c", "hotkey": "1"}
  ],
  "allow_empty": true,
  "multi_label": false,
  "instructions": "<p>Tight boxes around each object.</p>",
  "_meta": { "template_slug": "mixed", "mask_import_enabled": true }
}
```

## `Annotation.result` (JSON)

List of region objects. Normalized coordinates `0..1` relative to image width/height (top-left origin).

**Rectangle:**

```json
{"type": "rect", "label_id": "obj1", "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.25}
```

**Polygon:**

```json
{"type": "polygon", "label_id": "obj1", "points": [[0.1,0.1],[0.2,0.1],[0.2,0.2]]}
```

**Point:**

```json
{"type": "point", "label_id": "obj1", "x": 0.5, "y": 0.5}
```

**Classification (image-level):**

```json
{"type": "choices", "label_id": "obj1", "selected": ["class_a"]}
```

## Task denormalized fields

- `is_labeled`: true when `total_annotations >= overlap` and consensus/review rules satisfied (MVP: count non-cancelled submissions).
- `total_annotations`, `cancelled_annotations`: updated via signals.

## Indexes

- `Task(project, is_labeled)`, `Task(project, inner_id)`.
- `ImageAsset` GIST on `location` when not null.
- `TaskLock(expire_at)`.
