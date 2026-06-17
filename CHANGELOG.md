# Changelog

What changed for care-episode consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.8.2] - 2026-06-20

### Changed

- **Clinical risk alert email** — escalation notifications contain a deep link to the clinician patient record only (`patient_uuid` + `episode_uuid` query param). No PHI/PII in subject or body.
- **Chat interaction context** — optional `patient_display_name` on create-interaction and completion proxy requests; merged into interaction context for greeting. User service label lookup removed.

### Removed

- **`user_client`** — care-episode no longer calls User to resolve patient display names.

## [0.8.1] - 2026-06-19

### Changed

- **Patient identity from User registry** — `display_code` and `display_name` are no longer stored on `care_episode_recoveries` or returned on episode API payloads. Episodes store `patient_uuid` only; chat context and clinical escalation resolve labels from the User service at runtime.

### Removed

- **`display_code` / `display_name`** on `CareEpisode`, upsert/start request bodies, and episode history entries (migration **012**).

## [0.8.0] - 2026-06-18

### Added

- **Multi-episode lifecycle** — `episode_uuid` primary key, `status` (`active` / `closed`), and per-patient history; at most one active episode per patient.
- **`GET/PATCH /api/v1/care-episodes/{episode_uuid}`** — read and patch a specific episode (close/reopen via `status`).
- **`GET/POST /api/v1/care-episodes/{patient_uuid}/episodes`** — list history and start a new episode for a patient.
- **`POST /api/v1/care-episodes/bulk-close`** — close active episodes for multiple patients in one request.
- **`care_window_days`** on episodes (migration **010**).
- **Tenant-scoped Cedar** — clinicians may list and mutate care episodes only when `principal.tenantId` matches the episode or catalog tenant.

### Changed

- Recovery-oriented routes and OpenAPI names align on **episode** vocabulary (`/care-episodes`, not `/recoveries`); response field **`recovery_id`** is unchanged (external session id).
- Closure time is derived from **`changed_at`** when `status` is `closed`; redundant **`closed_at`** column removed (migration **011**).

### Removed

- **`POST /api/v1/care-episodes/recoveries`** and other legacy recovery path aliases — use catalog upsert and patient episode routes instead.

## [0.7.2] - 2026-06-17

### Changed

- Platform-client mesh wiring and clinical risk alert delivery via notification (see [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md)).

## [0.7.1] - 2026-06-16

### Fixed

- **`POST /api/v1/care-episodes/recoveries`** uses member-scoped Cedar entities from the request `patient_uuid`, so demo bootstrap can create a personal recovery for the signed-in user without operator catalog scope.

## [0.7.0] - 2026-06-14

### Changed

- Pinned **`authorization-in-the-middle/v0.7.1`** — SDK REST inference on care-episode routes; principals via `resolve_jwt_principal` with demo template patient attr.

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
