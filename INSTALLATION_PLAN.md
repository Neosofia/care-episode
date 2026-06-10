# Installation Plan — care-episode v0.3.0

Per-version deploy and verification steps for operators.

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.3.0` (tag `care-episode/v0.3.0`).
2. Deploy with existing env unchanged (SDK **`authorization-in-the-middle/v0.4.23`** baked into the image).
3. No new migrations in this release.

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.3.0"`.
2. `GET /api/v1/care-episodes/sessions` returns the clinician session roster for an authorized JWT.
3. `POST /api/v1/care-episodes/invites` still returns **201** with `invite_token`.

## Evidence

- Health version matches `0.3.0`.
- Session list and invite smoke checks pass.
