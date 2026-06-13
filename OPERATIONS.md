# Operations

## Local development

1. Sync dependencies:

   ```bash
   uv sync
   ```

2. Configure environment (copy `.env.example` to `.env`). Required: database URLs, `JWT_AUDIENCE=care-episode`, and `JWT_JWKS_URI` or `JWT_PUBLIC_KEY`. For chat proxy locally, also set **`CARE_EPISODE_CLIENT_SECRET`** and ensure authentication has `care-episode` credentials and a `chat` registry entry (see `cdp/scripts/seed_services.py`).

   Compose example (Postgres on host port **5015**):

   ```dotenv
   MIGRATION_DATABASE_URL=postgresql+psycopg://care_episode_template:change-me@localhost:5015/cdp_care_episode
   APP_DATABASE_URL=postgresql+psycopg://app:change-me@localhost:5015/cdp_care_episode
   JWT_JWKS_URI=http://localhost:8014/.well-known/jwks.json
   JWT_AUDIENCE=care-episode
   CARE_EPISODE_CLIENT_SECRET=change-me
   ```

3. Apply migrations:

   ```bash
   uv run alembic upgrade head
   ```

4. Run tests:

   ```bash
   uv run pytest -q
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

## Patient chat proxy

Channel clients (CDP patient chat UI, future SMS/app adapters) open chat through this service — not Chat directly:

| Step | Endpoint | Auth |
|------|----------|------|
| Open interaction | `POST /api/v1/care-episodes/{patient_uuid}/chat/interactions` | Patient JWT |
| Session start / turns | `POST …/chat/interactions/{chat_interaction_uuid}/completions` | Patient JWT (passthrough to Chat) |

Create uses a **care-episode service token** to Chat internally; completions forward the caller's patient JWT. Chat base URL is resolved from the authentication service registry (`slug: chat`). When Chat inference is unavailable, completions return **503** (passthrough); the patient UI shows an unavailable state — no stub replies.

Interaction create returns `care_episode_uuid` (active episode identifier; in the demo recovery model this equals `patient_uuid`) and `chat_interaction_uuid`.

## Clinical risk evaluation

After Chat persists a patient **content** turn, CE runs a dedicated risk agent (same OpenAI-compatible completions pattern as Chat inference). Skipped for `session_start`, empty content, and Chat **`intervention: true`** responses.

| Setting | Purpose |
|---------|---------|
| `INFERENCE_COMPLETIONS_URL` | Completions endpoint (e.g. Bedrock gateway) |
| `INFERENCE_API_KEY` | Bearer token for the gateway |
| `INFERENCE_MODEL` | Model id for risk evaluation |
| `INFERENCE_TEMPERATURE` | Default `0.2` |
| `RISK_ESCALATION_ENABLED` | Default `true`; `high` outcomes POST to notification |

When inference is unconfigured or unavailable, the completion still returns **200** from Chat; `risk_evaluation.risk_level` is `failed-pending-review` and recovery `risk_level` is unchanged. **`high`** is the only level that triggers escalation.

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
- **Audience:** `JWT_AUDIENCE` must include `care-episode`.
- **Chat proxy:** `CARE_EPISODE_CLIENT_SECRET` required in every environment that serves the patient chat proxy.
- **Healthcheck:** exempt `/health` from Talisman HTTPS redirect in forked deployments.

## Test matrix

- `tests/unit/` — business logic and route handlers with isolated patching.
- `tests/integration/` — OpenAPI contract, chat proxy happy path and no-recovery rejection (Chat HTTP stubbed).
- `tests/integration/test_container.py` — built image health against real Postgres.
