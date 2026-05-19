# UI specification

## Pages

| URL | Template | Purpose |
|-----|----------|---------|
| `/projects/{id}/` | `projects/project_detail.html` | Project overview, label datasets (list, create, upload links) |
| `/labeling/projects/{id}/` | `labeling/project_dashboard.html` | Stats, links to datasets and tasks |
| `/labeling/projects/{id}/datasets/create/` | `labeling/dataset_form.html` | Create dataset |
| `/labeling/projects/{id}/datasets/{ds_id}/upload/` | `labeling/dataset_upload.html` | Multi-file upload; redirects to project **Label datasets** after success |
| `/labeling/projects/{id}/tasks/{id}/` | `labeling/task.html` | Konva workspace |
| `/labeling/projects/{id}/schemas/` | `labeling/schema_list.html` | **Labeling setup:** templates by category, current setup row, toggle list visibility (admin) |
| `/labeling/projects/{id}/schemas/apply-template/` | — | **POST (admin):** replace setup from template slug |
| `/labeling/projects/{id}/schemas/edit/` | `labeling/schema_editor.html` | Guided steps + instructions + raw JSON / CodeMirror (admin) |
| `/labeling/projects/{id}/schema/` | — | Redirects to labeling setup list |
| `/labeling/projects/{id}/review/` | `labeling/review.html` | Reviewer queue (optional table) |

## `task.html` layout

- **Top bar (full width)**: link **Back to labeling**, live **status** text (`#label-status`), **image filename** (basename) when available, task id in muted text, optional **Instructions** button (opens modal when `schema.config.instructions` is set).
- **Body**: single main row — **left/flex-fill** is the Konva stage (`#label-stage` inside `#label-stage-wrapper`, sized to the container with letterboxed image); **no separate left metadata column**.
- **Right sidebar** (~300px, scrollable): **Labels** (schema label list with color swatch, name, hotkey), **Tools** (one control per entry in `schema.config.tools`; bounding box wired, other tools disabled with “not available” tooltip in MVP), optional shortcut hint, then **Submit** and **Skip / Next** (with hidden `next-url` for post-submit redirect).
- Draft still **autosaves** in the background (debounced); there is no separate Save draft button on the task page today.

## Default keyboard shortcuts (MVP)

| Key | Action |
|-----|--------|
| V | Select / move tool |
| B | Rectangle tool |
| P | Polygon tool |
| O | Point tool |
| C | Classify (toggle panel focus) |
| 1-9 | Select label by order |
| Del / Backspace | Delete selected shape |
| Ctrl+Z / Ctrl+Y | Undo / redo (client-side) |
| Ctrl+0 | Fit image to view |
| Esc | Cancel current polygon segment |

**Note:** Per-user custom hotkeys stored in `user` profile JSON in a later iteration; MVP uses defaults in `static/labeling/shortcuts.js`.

## Network

- Draft autosave: debounce 2s after last edit to `PUT /api/v1/tasks/{id}/draft/`.
- Submit: `POST /api/v1/tasks/{id}/annotations/` with `result` and optional `lead_time` seconds.
