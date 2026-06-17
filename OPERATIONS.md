# Operations

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `uv` | Python dependencies | [ADR-0005](https://github.com/Neosofia/cdp/blob/main/architecture/adrs/0005-use-uv-for-python-package-management.md) |
| Docker | Optional — `tests/integration/test_container.py` | [docs.docker.com](https://docs.docker.com/get-docker/) |

Protected routes need platform JWTs from a running **authentication** service (local port **8014**). Patient chat proxy locally also needs authentication registry entries for **`chat`** and **`care-episode`** credentials — see `cdp/scripts/seed_services.py`.

## Environment setup

Copy `.env.example` to `.env`.

| Variable | Purpose |
|----------|---------|
| `MIGRATION_DATABASE_URL` | Superuser URL for Alembic |
| `APP_DATABASE_URL` | Restricted `app` role at runtime |
| `JWT_AUDIENCE` | Expected JWT audience (`care-episode`) |
| `JWT_JWKS_URI` or `JWT_PUBLIC_KEY` | Verify platform JWTs |
| `CARE_EPISODE_CLIENT_SECRET` | Service token for Chat interaction create (required when exercising chat proxy) |

Optional settings (inference, escalation, timeouts, gunicorn): commented keys in `.env.example`.

Local example (Postgres on host port **5015** when using compose):

```dotenv
MIGRATION_DATABASE_URL=postgresql+psycopg://care_episode_template:change-me@localhost:5015/cdp_care_episode
APP_DATABASE_URL=postgresql+psycopg://app:change-me@localhost:5015/cdp_care_episode
JWT_JWKS_URI=http://localhost:8014/.well-known/jwks.json
JWT_AUDIENCE=care-episode
CARE_EPISODE_CLIENT_SECRET=change-me
```

## Local development

1. Sync dependencies:

   ```bash
   uv sync
   ```

2. Configure environment (see [Environment setup](#environment-setup)).

3. Apply migrations:

   ```bash
   uv run alembic upgrade head
   ```

4. Run tests:

   ```bash
   uv run pytest -q
   RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_container.py -q
   ```

5. Start the service (default port **8015**):

   ```bash
   uv run --dev -m gunicorn -c src/gunicorn.py src.app:app
   curl http://localhost:8015/health
   ```

6. Local JWT for protected routes:

   ```bash
   uv run scripts/gen_dev_jwt.py --type Patient --sub p1
   ```

## Full stack (compose)

Run with authentication, chat, and the rest of the platform from the CDP compose project:

- Copy `.care-episode.env.sample` → `.care-episode.env` and `.care-episode-postgres.env.sample` → `.care-episode-postgres.env`.
- Ensure authentication `JWT_WEB_AUDIENCE` includes `care-episode`.
- Build and start from the CDP repo: `docker compose -f docker-compose.local.yml up -d --build` (see [CDP OPERATIONS.md](https://github.com/Neosofia/cdp/blob/main/OPERATIONS.md)).

Service listens on **8015** (CDP spec 015 → port 8000 + 15). Postgres on host port **5015**.

## Docker build and run

From this repository:

```bash
docker build --target runtime -t care-episode:local .
docker run -d --rm -p 8015:8015 -e ENV=development --env-file .env --name care-episode-dev care-episode:local
```

Run migrations before or via `preDeployCommand` (see `railway.toml`).

## Public cloud deployment

Shared JWT, JWKS, CORS, healthcheck, and PaaS networking guidance:

**→ [infrastructure/public-cloud/OPERATIONS.md](https://github.com/Neosofia/infrastructure/blob/main/public-cloud/OPERATIONS.md)**

**Service-specific notes:**

- **Port:** `8015` (override with `PORT`).
- **Audience:** `JWT_AUDIENCE` must include `care-episode`; authentication must list `care-episode` in `JWT_WEB_AUDIENCE`.
- **JWKS:** Point `JWT_JWKS_URI` at the authentication service (private mesh URL in cloud, not localhost).
- **CORS:** Set `FRONTEND_URL` to the CDP UI origin.
- **Chat proxy:** `CARE_EPISODE_CLIENT_SECRET` required in every environment that serves patient chat.
- **Healthcheck:** Exempt `/health` from Talisman HTTPS redirect in forked deployments.
