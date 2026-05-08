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
| Run Django management commands | `docker compose exec app python manage.py <command>` |
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

## Tests

```bash
# Requires the database to be up (e.g. `docker compose up -d db` or full stack)
docker compose run --rm app pytest
```

## Project layout (high level)

- `app/` — Django project (`manage.py`, `main/`, `labeling/`, `projects/`, `user/`, …)
- `nginx/` — nginx image and config (proxies to the app, serves `/static/`, `/media/`)
- `docs/` — product and technical documentation
- `docker-compose.yml` — `db` (PostGIS), `app`, `nginx`
- `entrypoint.sh` — waits for Postgres, `collectstatic`, `makemigrations` / `migrate`, then the container command

For architecture, API, and data model details, see [docs/README.md](docs/README.md).
