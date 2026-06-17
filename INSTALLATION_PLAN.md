# Installation Plan — care-episode v0.8.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.8.0` (tag `care-episode/v0.8.0`).
2. Run migrations to head (revisions **`009`**–**`011`**: multi-episode model, `care_window_days`, drop `closed_at`).
3. Redeploy **CDP UI 2026.06.18** (or later) in the same change window — clinician episode close/reopen and history UI depend on the new routes.
4. Ensure **notification** is registered when **`RISK_ESCALATION_ENABLED`** is true (unchanged from v0.7.x).

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.8.0"`.
2. `SELECT version_num FROM alembic_version` reports **`011`**.
3. Clinician JWT with `neosofia:tenant_uuid` can `GET /api/v1/care-episodes?tenant_uuid=<tenant>` and `PATCH /api/v1/care-episodes/{episode_uuid}` for a same-tenant patient; cross-tenant catalog or member access returns **403**.
4. `GET /api/v1/care-episodes/{patient_uuid}/episodes` returns history with at most one `is_current` active row.

## Evidence

- Health version **0.8.0**; migration **011** applied; Cedar `authorization.allowed` logs show matching `tenant_uuid` on catalog and member routes.

---

# Installation Plan — care-episode v0.7.2

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.7.2` (tag `care-episode/v0.7.2`).
2. No new migrations.
3. Ensure **notification** is registered in the service registry (`slug: notification`) when **`RISK_ESCALATION_ENABLED`** is true (default).
4. Optional: set **`CLINICAL_RISK_ALERT_FROM_EMAIL`** (default `care-episode-alerts@neosofia.tech`).
5. Review gunicorn and upstream timeout env vars if overridden locally (defaults: **`WEB_CONCURRENCY=1`**, **`GUNICORN_THREADS=32`**, **`GUNICORN_TIMEOUT=15`**; mesh hops **`CHAT_SERVICE_TIMEOUT_SECONDS`**, **`INFERENCE_TIMEOUT_SECONDS`**, **`NOTIFICATION_SERVICE_TIMEOUT_SECONDS`**, **`AUTHENTICATION_TOKEN_TIMEOUT_SECONDS`** default **10**).

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.7.2"`.
2. High-risk chat completion triggers a clinical alert email via notification (`POST /api/emails`) when escalation is enabled.

## Evidence

- Health version **0.7.2**; structured logs show successful chat proxy and risk evaluation outcomes.

---

# Installation Plan — care-episode v0.7.1

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.7.1` (tag `care-episode/v0.7.1`).
2. No new migrations or env vars.

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.7.1"`.
2. Demo workspace bootstrap completes `POST /api/v1/care-episodes` for the signed-in demo user (201, not 403).

## Evidence

- Health version **0.7.1**; demo bootstrap recovery create succeeds on staging.

---

# Installation Plan — care-episode v0.7.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.7.0` (tag `care-episode/v0.7.0`).
2. No new migrations or env vars (SDK **`authorization-in-the-middle/v0.7.1`** only).

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.7.0"`.
2. Chat proxy interaction create and completion proxy smoke checks pass.

## Evidence

- Health version **0.7.0**; structured logs show successful chat proxy outcomes.

---

# Installation Plan — care-episode v0.6.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.6.0` (tag `care-episode/v0.6.0`).
2. Run migrations to head (revision **`008`** — `interaction_risk_states`; risk level on `care_episode_recoveries`).
3. Set **`INFERENCE_COMPLETIONS_URL`**, **`INFERENCE_API_KEY`**, and **`INFERENCE_MODEL`** for clinical risk evaluation (same gateway pattern as Chat inference).
4. Keep **`CARE_EPISODE_CLIENT_SECRET`** and Chat registry entry from prior releases.
5. Optional: set **`RISK_ESCALATION_ENABLED=false`** to disable high-risk email alerts. Ensure **notification** is registered in the service registry (`slug: notification`) so CE can reach `POST /api/emails`.

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.6.0"`.
2. Patient content completion → **200** with Chat reply and `risk_evaluation` object (`risk_level`, `escalated`).
3. `session_start` completion → **200** without `risk_evaluation`.
4. With inference env unset, content completion → `risk_evaluation.risk_level` is `failed-pending-review`.

## Evidence

- Health version matches `0.6.0`.
- Migration `008` applied.
- Structured logs show `risk_evaluation` / `risk_escalation` events (outcome only; no PHI).

---

## care-episode v0.5.0

1. Pull image `ghcr.io/neosofia/care-episode:v0.5.0` (tag `care-episode/v0.5.0`).
2. Deploy **chat v0.5.0** in the same change window (CE proxy depends on CE-only interaction create).
3. Set **`CARE_EPISODE_CLIENT_SECRET`** (client credentials for `care-episode` → authentication token exchange).
4. Ensure **Chat** is registered in the authentication service registry (`slug: chat`) with a reachable `base_url`.
5. Keep existing database URLs, JWT, and Cedar settings unless your environment customizes them.
6. Run migration **`006`** if upgrading from v0.4.0 (recovery rename).

**Verify:** `GET /health` → `"version": "0.5.0"`; chat interaction create and completion proxy smoke checks pass.

---

## care-episode v0.3.0

1. Pull image `ghcr.io/neosofia/care-episode:v0.3.0` (tag `care-episode/v0.3.0`).
2. Deploy with existing env unchanged (SDK **`authorization-in-the-middle/v0.4.23`** baked into the image).
3. No new migrations in this release.

**Verify:** `GET /health` → `"version": "0.3.0"`; recovery list and invite smoke checks pass.
