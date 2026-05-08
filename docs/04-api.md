# REST API

Base path: `/api/v1/`

## Auth

- **Session** authentication for browser (`SessionAuthentication`).
- **CSRF** required for unsafe methods from JS (`X-CSRFToken` header).

## Projects & membership

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/` | List projects the user can access |
| GET | `/projects/{id}/` | Project detail |
| GET, POST | `/projects/{id}/members/` | List / add members (admin) |
| GET, PATCH, DELETE | `/projects/{id}/members/{user_id}/` | Update role / remove |

## Labeling (nested under project)

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `/projects/{id}/labeling_datasets/` | Datasets |
| GET, POST | `/projects/{id}/labeling_datasets/{ds_id}/images/` | Upload metadata / list images |
| GET | `/projects/{id}/tasks/` | List tasks (filters) |
| GET | `/projects/{id}/tasks/next/` | Next available task for current user |
| POST | `/tasks/{id}/lock/` | Acquire or refresh lock |
| POST | `/tasks/{id}/unlock/` | Release lock |
| GET, PUT, PATCH | `/tasks/{id}/draft/` | Current user's draft |
| GET, POST | `/tasks/{id}/annotations/` | List / create annotation (submit) |
| PATCH | `/annotations/{id}/` | Set review status: `submitted` / `approved` / `rejected` / `needs_revision` (reviewer or owner) |
| POST | `/projects/{id}/export/` | ZIP export (include `variants` or query `include=`) |

## Pagination

- `page` and `page_size` (default 20, max 100).

## OpenAPI

- Schema: `/api/schema/`
- Swagger UI: `/api/docs/`
