# Installation Plan — care-episode v0.4.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.4.0` (tag `care-episode/v0.4.0`).
2. Deploy **chat v0.5.0** in the same change window (CE proxy depends on CE-only interaction create).
3. Set **`CARE_EPISODE_CLIENT_SECRET`** (client credentials for `care-episode` → authentication token exchange).
4. Ensure **Chat** is registered in the authentication service registry (`slug: chat`) with a reachable `base_url`.
5. Keep existing database URLs, JWT, and Cedar settings unless your environment customizes them.
6. No new migrations in this release.

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.4.0"`.
2. Authorized patient JWT: `POST /api/v1/care-episodes/{patient_uuid}/chat/interactions` → **201** with `care_episode_uuid` and `chat_interaction_uuid`.
3. Unknown patient (no session row): same path → **404** (Chat must not be called).
4. `POST …/chat/interactions/{chat_interaction_uuid}/completions` with patient JWT and `session_start: true` → **200** when Chat inference is configured; **503** when inference is down (passthrough from Chat; UI shows unavailable).

## Evidence

- Health version matches `0.4.0`.
- Chat interaction create and completion proxy smoke checks pass against pinned images.
- Structured logs show `chat_interaction_create` / `chat_completion_proxy` events with outcome only (no PHI).

---

## care-episode v0.3.0

1. Pull image `ghcr.io/neosofia/care-episode:v0.3.0` (tag `care-episode/v0.3.0`).
2. Deploy with existing env unchanged (SDK **`authorization-in-the-middle/v0.4.23`** baked into the image).
3. No new migrations in this release.

**Verify:** `GET /health` → `"version": "0.3.0"`; session list and invite smoke checks pass.
