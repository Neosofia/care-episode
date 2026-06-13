# Changelog

What changed for care-episode consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.6.0] - 2026-06-11

### Added

- **Clinical risk agent** — after each patient message completion (not `session_start` or Chat `intervention` turns), CE evaluates risk via an OpenAI-compatible completions API using a fixed in-service prompt.
- Rolling **interaction summary** per `chat_interaction_uuid` (`interaction_risk_states`, migration `007`); evaluated **risk level** is stored on `care_episode_recoveries.risk_level`.
- Completion proxy responses may include **`risk_evaluation`** (`risk_level`, `escalated`).
- Recovery **`risk_level`** updates on each successful evaluation (`low` / `medium` / `high`; inference failure → `failed-pending-review` in the API response only).
- **`interaction_risk_states`** holds the current rolling summary per interaction; prior values live in the standard audit history (`audit.setup_tracking`).
- Migration **`008`** drops legacy idempotency columns on existing databases and rebuilds audit tracking.
- **`high`** triggers clinical escalation handoff to notification (`POST /api/v1/escalations`) when `RISK_ESCALATION_ENABLED` is true.
- Inference settings: `INFERENCE_COMPLETIONS_URL`, `INFERENCE_API_KEY`, `INFERENCE_MODEL`, optional `INFERENCE_TEMPERATURE`.

## [0.5.0] - 2026-06-11

### Changed

- Renamed **session** terminology to **recovery** across API, database, and docs — post-discharge monitoring period for a care episode.
- **`GET/POST /api/v1/care-episodes/recoveries`** replaces `/sessions` (list and upsert).
- Response and request field **`recovery_id`** replaces `session_id`.
- Table **`care_episode_recoveries`** replaces `care_episode_sessions` (migration `006`).
- Chat proxy telemetry outcome **`no_recovery`** replaces `no_session`.

## [0.4.0] - 2026-06-11

### Added

- **Patient chat proxy** — `POST /api/v1/care-episodes/{patient_uuid}/chat/interactions` validates an active recovery, builds authoritative interaction context, and creates a Chat interaction via service token.
- **Completions proxy** — `POST …/chat/interactions/{chat_interaction_uuid}/completions` forwards the patient JWT to Chat for session start and message turns.
- Mesh clients for authentication token exchange, service registry discovery, and Chat HTTP calls.
- PHI-safe structured telemetry on chat proxy routes (`chat_interaction_create`, `chat_completion_proxy`).

### Changed

- Interaction create responses include **`care_episode_uuid`** (demo recovery model: equals `patient_uuid`).

## [0.3.0] - 2026-06-10

### Changed

- Cedar catalog reads use **`care-episode:list`**; removed `src/bootstrap/capabilities.py` and `_READ`/`_WRITE` decorator bundles.
- `@with_security` routes use REST inference or inline `action='Action::"…"'` only.
- Pinned **`authorization-in-the-middle/v0.4.23`**.
