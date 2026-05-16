# ISR Label

Django-based image annotation platform (projects, geolocated assets, labeling tasks, exports). The stack runs in Docker: **PostGIS**, **Django**, and **nginx** (reverse proxy on port 80).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- A `.env` file in the project root (not committed). It must define database credentials and any app secrets; the DB service healthcheck expects a user and database name consistent with your variables (see `docker-compose.yml`).

## Quick start

```bash
# Build images and start all services (detached)
docker compose up -d --build

# Open the app (nginx → Django on app:8000)
open http://localhost
```

## Common Docker Compose commands

| Action | Command |
|--------|---------|
| Start stack (foreground, logs) | `docker compose up` |
| Start in background | `docker compose up -d` |
| Rebuild after Dockerfile or dependency changes | `docker compose up -d --build` |
| Stop and remove containers | `docker compose down` |
| Stop and remove containers + named volumes (wipes DB) | `docker compose down -v` |
| Follow logs (all services) | `docker compose logs -f` |
| Logs for one service | `docker compose logs -f app` or `docker compose logs -f db` |
| Shell inside the app container | `docker compose exec app bash` |
| Run tests (pytest, one-off container) | `docker compose up -d db` then `docker compose run --rm app python -m pytest` |
| Run tests (reuse running `app`) | `docker compose exec app python -m pytest` |
| One-off app container (fresh entrypoint: migrate, then command) | `docker compose run --rm app <command>` |

## Django in Docker

```bash
# Migrations (usually run automatically on `app` start via entrypoint)
docker compose exec app python manage.py makemigrations
docker compose exec app python manage.py migrate

# Create a superuser
docker compose exec app python manage.py createsuperuser

# Django shell
docker compose exec app python manage.py shell
```

## Tests (Docker Compose)

Run the test suite **inside the app container** so GDAL/PostGIS match production and you do not need a local Python/GDAL install.

**Prerequisites:** the `db` service must be reachable. The easiest way is to start it first (or bring up the full stack):

```bash
docker compose up -d db
```

**One-off test run** (starts a temporary `app` container; the image **entrypoint** waits for Postgres, runs `collectstatic`, `makemigrations` / `migrate`, then runs your command). First run after an image change can take a minute:

```bash
# All tests (pytest discovers tests under the mounted ./app tree)
docker compose run --rm app python -m pytest

# Single app / path
docker compose run --rm app python -m pytest labeling/ -q

# Django’s test runner (alternative)
docker compose run --rm app python manage.py test
docker compose run --rm app python manage.py test labeling
```

**Faster iteration** when the stack is already up (reuses the long-running `app` container; **skips** the entrypoint on each invocation):

```bash
docker compose up -d   # db + app (+ nginx if you need it)
docker compose exec app python -m pytest
docker compose exec app python -m pytest labeling/ -q
docker compose exec app python manage.py test labeling
```

**Troubleshooting**

- If `run` fails with database connection errors, ensure `docker compose ps` shows `db` as healthy: `docker compose up -d db` and wait for the healthcheck.
- Tests use the **same** Postgres service as dev by default; Django’s test runner uses a separate test database name when configured in settings (see `main/settings.py`).

## Project layout (high level)

- `app/` — Django project (`manage.py`, `main/`, `labeling/`, `projects/`, `user/`, …)
- `nginx/` — nginx image and config (proxies to the app, serves `/static/`, `/media/`)
- `docs/` — product and technical documentation
- `docker-compose.yml` — `db` (PostGIS), `app`, `nginx`
- `entrypoint.sh` — waits for Postgres, `collectstatic`, `makemigrations` / `migrate`, then the container command

For architecture, API, and data model details, see [docs/README.md](docs/README.md).
