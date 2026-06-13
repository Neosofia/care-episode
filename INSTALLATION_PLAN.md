# Installation Plan — care-episode v0.6.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.6.0` (tag `care-episode/v0.6.0`).
2. Run migrations to head (revision **`008`** — `interaction_risk_states`; risk level on `care_episode_recoveries`).
3. Set **`INFERENCE_COMPLETIONS_URL`**, **`INFERENCE_API_KEY`**, and **`INFERENCE_MODEL`** for clinical risk evaluation (same gateway pattern as Chat inference).
4. Keep **`CARE_EPISODE_CLIENT_SECRET`** and Chat registry entry from prior releases.
5. Optional: set **`RISK_ESCALATION_ENABLED=false`** to disable notification handoff until notification ships `POST /api/v1/escalations`.

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
