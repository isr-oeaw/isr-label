# Phase plan & acceptance

## Phase 0 — Foundation

- [x] `docs/*` as listed in `README.md`
- [x] `requirements.txt` extended; `settings` PostGIS + apps
- [x] `docker-compose.yml` → PostGIS image

**Acceptance:** `manage.py check` passes; `migrate` runs on empty PostGIS database.

## Phase 1 — Membership

- [x] `ProjectMembership` model; data migration from `collaborators` + owner
- [x] Remove `collaborators` M2M; update views/queries
- [x] Member management UI
- [x] `projects.admin` no longer references missing `datasets` relation; use `labeling_datasets` count if present

**Acceptance:** Existing projects show correct members; owner is admin; old collaborators are annotators.

## Phase 2 — Labeling core

- [x] `labeling` app models, signals, services (EXIF, queue, locks)

**Acceptance:** Create dataset → upload image → task created → can lock/draft/annotate in shell or admin.

## Phase 3 — API + UI

- [x] DRF routers + OpenAPI
- [x] Static Konva/JS + templates

**Acceptance:** Browser can complete one full label cycle; map shows point when GPS exists.

## Phase 4 — Review, export, consensus, tests

- [x] Review states + `review.html` minimal
- [x] ZIP export
- [x] `consensus` management command
- [x] Tests + i18n strings for new UI

**Acceptance:** `pytest` green; sample export unzips with expected files.
