# Changelog

What changed for care-episode consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.4.0] - 2026-06-11

### Added

- **Patient chat proxy** — `POST /api/v1/care-episodes/{patient_uuid}/chat/interactions` validates an active session, builds authoritative interaction context, and creates a Chat interaction via service token.
- **Completions proxy** — `POST …/chat/interactions/{chat_interaction_uuid}/completions` forwards the patient JWT to Chat for session start and message turns.
- Mesh clients for authentication token exchange, service registry discovery, and Chat HTTP calls.
- PHI-safe structured telemetry on chat proxy routes (`chat_interaction_create`, `chat_completion_proxy`).

### Changed

- Interaction create responses include **`care_episode_uuid`** (demo session model: equals `patient_uuid`).

## [0.3.0] - 2026-06-10

### Changed

- Cedar catalog reads use **`care-episode:list`**; removed `src/bootstrap/capabilities.py` and `_READ`/`_WRITE` decorator bundles.
- `@with_security` routes use REST inference or inline `action='Action::"…"'` only.
- Pinned **`authorization-in-the-middle/v0.4.23`**.
