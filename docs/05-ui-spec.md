# UI specification

## Pages

| URL | Template | Purpose |
|-----|----------|---------|
| `/labeling/projects/{id}/` | `labeling/project_dashboard.html` | Stats, links to datasets, map, tasks |
| `/labeling/projects/{id}/datasets/` | `labeling/dataset_list.html` | List datasets + create |
| `/labeling/projects/{id}/datasets/{ds_id}/upload/` | `labeling/dataset_upload.html` | Multi-file upload |
| `/labeling/projects/{id}/map/` | `labeling/map.html` | Leaflet map of images |
| `/labeling/tasks/{id}/` | `labeling/task.html` | Konva workspace |
| `/labeling/projects/{id}/schema/` | `labeling/schema_editor.html` | Edit active schema config (admin) |
| `/labeling/projects/{id}/review/` | `labeling/review.html` | Reviewer queue (optional table) |

## `task.html` layout

- **Left column**: project title, task id, image filename, help link for shortcuts.
- **Center**: Konva `Stage` with image as background, zoom (wheel at cursor), pan (space+drag or middle button).
- **Right column**: label list with color + hotkey `1-9`, tool buttons (classify, rect, poly, point).
- **Bottom bar**: Save draft, Submit, Skip, **Next** (if API allows).

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
