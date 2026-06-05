# Installation Plan — care-episode v0.2.3

## Deploy steps

1. Pull image `ghcr.io/neosofia/care-episode:v0.2.3` (tag `care-episode/v0.2.3`).
2. Run migrations before starting the new runtime container:

   ```bash
   uv run alembic upgrade head
   ```

   Applies revision `005`, which drops legacy `care_episode_transcripts` tables and history view. Chat transcripts now live in the chat service.

3. Deploy the care-episode service with existing env unchanged.

## Post-deploy verification

1. `GET /health` returns `"status": "ok"` and `"version": "0.2.3"`.
2. `GET /api/v1/care-episodes/sessions` returns the clinician session roster.
3. Demo clone endpoint still works for template patient seeding when invoked by CDP seed scripts.

## Staging reseed

After chat and care-episode are live, **re-run the CDP demo seed** (`scripts/seed_demo_platform.py` or equivalent staging job) so patients, episodes, and chat threads align with the new interaction model. Existing staging chat rows keyed to the old message shape are not migrated in place.

## Evidence

- Migration `alembic current` shows head `005`.
- Health version matches `0.2.3`.
- Session list and clone-demo smoke checks pass.
