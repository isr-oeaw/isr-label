# ISR Label - Documentation

Design and specifications for the annotation platform. Read in order:

1. [00-overview.md](00-overview.md) — goals, non-goals, glossary
2. [labeling/data-model.md](labeling/data-model.md) — labeling ERD pointer (see also 03-data-model)
3. [01-research-image-labeling.md](01-research-image-labeling.md) — UI patterns, Label Studio–style concepts
4. [02-architecture.md](02-architecture.md) — app boundaries, stack
5. [03-data-model.md](03-data-model.md) — ERD, JSON field contracts
6. [04-api.md](04-api.md) — REST API
7. [05-ui-spec.md](05-ui-spec.md) — pages, keyboard shortcuts, Konva tools
8. [06-permissions.md](06-permissions.md) — project roles, membership
9. [07-geo.md](07-geo.md) — EXIF, PostGIS, Leaflet
10. [08-export-formats.md](08-export-formats.md) — COCO, YOLO, GeoJSON
11. [09-phase-plan.md](09-phase-plan.md) — implementation phases and acceptance criteria

**Convention:** product decisions and runbooks live in `docs/`; code lives under `app/`.
