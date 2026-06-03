# Python Service Template

Reference Flask service template with:

- typed startup configuration via `pydantic-settings`
- service-owned Cedar policies loaded from `policies/`
- structured JSON logging via `logenvelope`
- security headers via `flask-talisman`
- per-route rate limiting via `flask-limiter`
- `/health` plus versioned `/api/v1/*` routes

## Quickstart

```bash
uv sync
uv run --dev -m pytest -q
python -m gunicorn -c gunicorn_conf.py main:app
```

## Source Override

This template currently resolves `authorization-in-the-middle` from the local monorepo checkout via `[tool.uv.sources]` in `pyproject.toml`.

When you copy this template into a standalone repository, replace that local source override with an immutable published wheel URL before enabling container builds or CI.

## Endpoints

- `GET /health`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/summary`
- `DELETE /api/v1/documents/{document_id}`

The machine-readable contract lives in `openapi.json`.

## Database

Migration `000` bootstraps PostgreSQL for a backing store: creates the restricted `app` role (password from `APP_DATABASE_URL`), grants table privileges, and applies the shared [audit SQL templates](https://github.com/Neosofia/templates/tree/main/sql/audit). Use a two-URL pattern: superuser for migrations, `app` for runtime.

```bash
uv run alembic upgrade head
```

## Environment Variables

| Variable | Type | Default | Effect |
|---|---|---|---|
| `MIGRATION_DATABASE_URL` | string | *(required)* | Superuser URL for Alembic migrations. |
| `APP_DATABASE_URL` | string | *(required)* | Restricted `app` role URL for the running service. |
| `JWT_AUDIENCE` | string | `python-template` | Audience to expect on JWT.  |
| `ENV` | string | `production` | Controls development/test behavior such as HTTPS enforcement. |
| `LOG_LEVEL` | string | `info` | Minimum structured log severity. |
| `PORT` | integer | `8900` | HTTP listener port (demo scaffold; outside 8000+spec range). |
| `TRUSTED_PROXY_HOPS` | integer | `1` | Number of trusted reverse proxies for `ProxyFix`. |
| `AUTHORIZATION_POLICIES_DIR` | path | `policies` | Directory containing Cedar policy files (`*.cedar`). |
| `AUTHORIZATION_POLICY_CACHE_TTL` | integer | `60` | Seconds to cache the loaded policy bundle in process. |
| `MAX_CONTENT_LENGTH` | integer | `16384` | Maximum accepted request body size in bytes. |
| `RATELIMIT_STORAGE_URI` | string | `memory://` | Rate-limit backend. Use Redis in multi-replica deployments. |
| `HEALTH_RATE_LIMIT` | string | `600 per minute` | Health endpoint rate limit. |
| `DOCUMENT_READ_RATE_LIMIT` | string | `60 per minute` | Read-route rate limit. |
| `DOCUMENT_DELETE_RATE_LIMIT` | string | `10 per minute` | Delete-route rate limit. |
| `WEB_CONCURRENCY` | integer | `2` | Gunicorn worker count. |
| `GUNICORN_THREADS` | integer | `2` | Gunicorn thread count per worker. |
| `GUNICORN_TIMEOUT` | integer | `30` | Gunicorn worker timeout in seconds. |
| `GUNICORN_KEEPALIVE` | integer | `5` | Gunicorn keepalive in seconds. |

## Testing

```bash
uv run --dev -m pytest -q
uv run --dev -m pytest tests/contract -q
RUN_DOCKER_TESTS=1 uv run --dev -m pytest tests/integration -q
```

The default pytest invocation enforces an 80% coverage floor and excludes integration tests from the fast unit/contract path.

## Container Build

In this monorepo, build the reference container from the repository root so the local `authorization-in-the-middle` source override is available during `uv sync`:

```bash
docker build -f templates/python/service/Dockerfile -t python-template:test .
```
