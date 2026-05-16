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
9. [07-geo.md](07-geo.md) — EXIF, PostGIS, image coordinates
10. [08-export-formats.md](08-export-formats.md) — COCO, YOLO
11. [09-phase-plan.md](09-phase-plan.md) — implementation phases and acceptance criteria
12. [10-segmentation-import.md](10-segmentation-import.md) — raster mask → polygon import (CLI + API), polygon-first policy product decisions and runbooks live in `docs/`; code lives under `app/`.

## Running tests (Docker Compose)

Run the suite **inside the app container** from the **repository root** so GDAL, GEOS, and PostGIS match the deployed stack. A local Python install without those libraries is usually not enough for the full test run.

**Database up:** the `db` service must be reachable (healthcheck passing).

```bash
docker compose up -d db
```

**One-off run** (new `app` container each time; entrypoint waits for Postgres, runs migrations, then your command—first run after an image change can be slow):

```bash
docker compose run --rm app python -m pytest
docker compose run --rm app python -m pytest labeling/ -q
docker compose run --rm app python manage.py test labeling
```

**Reuse a running `app`** (faster while developing; stack already up with `docker compose up -d`):

```bash
docker compose exec app python -m pytest
docker compose exec app python manage.py test labeling
```

After changing the **Dockerfile** or **Python dependencies**, rebuild before testing: `docker compose build app` or `docker compose up -d --build`.

More detail, alternative commands, and troubleshooting: **Tests (Docker Compose)** in the repository [README.md](../README.md).
