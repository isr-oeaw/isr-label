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

## `labeling.LabelSchema.config` (JSON)

Example:

```json
{
  "tools": ["classification", "rect", "polygon", "point"],
  "labels": [
    {"id": "obj1", "name": "Object", "color": "#e74c3c", "hotkey": "1"}
  ],
  "allow_empty": true,
  "multi_label": false
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
