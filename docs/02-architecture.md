# Architecture

## Apps

| App | Responsibility |
|-----|----------------|
| `user` | `CustomUser`, `Role`, allauth |
| `pages` | Home, announcements |
| `projects` | `Project`, `ProjectMembership` |
| `labeling` | Datasets, images, tasks, annotations, API surface |
| `main` | Settings, root URLs, middleware |

## Data flow (annotation)

1. **Upload**: Browser POST → Django view creates `ImageAsset` (+EXIF) → may create `Task` for active schema.
2. **Label**: User opens `Task` page → client loads image + `LabelSchema.config` + draft JSON → Konva edits → debounced `PATCH` draft.
3. **Submit**: `POST` creates `Annotation`, updates task counters, releases lock.
4. **Export**: `POST` export assembles ZIP (COCO / YOLO) from `Annotation.result`.

## API

- **Django REST Framework** with session auth for same-origin app; optional `SessionAuthentication` + `CSRF` for forms + fetch.
- **drf-spectacular** for OpenAPI at `/api/schema/` and UI at `/api/docs/`.
- **Nested resources** under `/api/v1/projects/{id}/` where practical.

## Database

- **PostGIS** (GeoDjango) for `ImageAsset.location` (`PointField`, SRID 4326).
- Development `docker-compose` uses `postgis/postgis:16-3.4` to match production.

**Tests:** use Docker Compose (`app` container + `db`) so GIS libraries and the database match this stack; see [Running tests (Docker Compose)](README.md#running-tests-docker-compose) in `docs/README.md`.

## Storage

- Default: `MEDIA_ROOT` local. Production can switch to S3/MinIO later without changing model layer.
