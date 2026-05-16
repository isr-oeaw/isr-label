# Research: Image Labeling & UI

## Industry patterns (Label Studio / CVAT)

- **Hierarchy**: Project → media → task → annotation(s), with optional overlap and review.
- **Task payload**: Opaque `data` JSON (e.g. image URL) + optional `is_labeled` denormalized flag.
- **Result**: JSON list of regions (boxes, polygons, points, choices) in image or normalized coordinates.
- **Drafts**: Autosave before submit; crash recovery.
- **Locks**: Short TTL so two annotators rarely work the same task simultaneously.
- **UX**: Keyboard-first (number keys for classes, V select, B box, P polygon, undo/redo, fit-to-screen).

## Frontend stack (this project)

- **Canvas**: [Konva.js](https://konvajs.org/) for 2D shapes, pan/zoom, transformers.
- **Styling**: Existing Bootstrap 5; annotation shell is a full-width template with a three-column + toolbar layout.

## Export priorities

- **YOLO**: Normalized `cx, cy, w, h` per class — first for detection pipelines.
- **COCO**: Single JSON with `images` / `annotations` / `categories` — interop with CV tooling.
- **GIS / map tie-in**: When `location` exists on an image, coordinates live on `ImageAsset`; labels remain in normalized image space in `Annotation.result`.

## References (external)

- Label Studio data model patterns (Task, Annotation, Draft, Lock).
- Konva image labeling [sandbox](https://konvajs.org/docs/sandbox/Image_Labeling.html) as interaction reference.
