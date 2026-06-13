# Care Episode Service — Security Posture

This service follows the [Neosofia Service Security Baseline](https://github.com/Neosofia/templates/blob/main/python/service/SECURITY.md) for transport, JWT validation, rate limiting, logging, container hardening, and CI controls. Platform-wide PHI containment and identity principles are in [CDP SECURITY.md](https://github.com/Neosofia/cdp/blob/main/SECURITY.md).

This document covers only what is specific to the Care Episode Service.

The Care Episode Service is the **authoritative store for procedure-scoped care windows** — recovery summaries, demo enrichment, invite linkage, and episode-shaped context consumed by Chat and clinician experiences. It does not store message transcripts.

To report any security-related issue please email security@neosofia.tech — do not create a public issue.

---

## Role in the Platform

| Concern | This service | Owner elsewhere |
|---------|--------------|-----------------|
| Care episode / session grouping | **Source of truth** (demo recovery model) | — |
| Message transcripts | — | **Chat** |
| JWT issuance | — | **Authentication** |
| Tier-2 roles and user registry | — | **User** |
| Interaction `context` for AI / risk | Builds snapshot at create; Chat persists | **Chat** (storage), **Care Episode** (authoring) |

---

## Trust Boundaries

| Boundary | Control |
|----------|---------|
| Caller identity | Platform JWT from **Authentication** |
| Authorization | Fail-closed Cedar in `policies/policy.cedar`, evaluated in-process via `authorization-in-the-middle` |
| Public surface | Only `GET /health` is unauthenticated |
| Patient chat proxy | `POST …/chat/interactions` — recovery row must exist before any Chat HTTP call |
| Context injection | Interaction `context` is built server-side from session fields; clients must not supply Chat context on create |
| S2S to Chat | `CARE_EPISODE_CLIENT_SECRET` → authentication `client_credentials` with `audience=chat` for interaction create only |
| Completions proxy | Patient JWT is forwarded to Chat; CE validates session existence only |
| Service discovery | Chat `base_url` resolved from authentication service registry (`slug: chat`) |

---

## Authorization (Cedar)

Policy bundle: `policies/policy.cedar`. Entity payloads are built in `src/authorization/entities.py`.

Authorized human principals may `care-episode:list` and `care-episode:create` on care-episode resources. Chat proxy routes use `care-episode:create` with the patient-scoped path as the authorization surface.

---

## Sensitive Data

| Data | In API / DB | In logs |
|------|-------------|---------|
| Session display names, procedure labels | Yes (PHI-adjacent) | **No** |
| Patient / episode UUIDs | Yes | Correlation ids only |
| Interaction `context` field values | Forwarded to Chat at create | **No** |
| Chat completion payloads | Passthrough only | **No** |

Structured telemetry on chat proxy routes uses `chat_interaction_create` and `chat_completion_proxy` — operation, status, and outcome only.

---

## Deployment Requirements

| Setting | Requirement |
|---------|-------------|
| `JWT_AUDIENCE` | Must include `care-episode` |
| `JWT_JWKS_URI` / `JWT_PUBLIC_KEY` | Authentication JWKS or PEM — same trust chain as other platform APIs |
| PostgreSQL (`APP_DATABASE_URL`) | Required |
| `AUTHORIZATION_POLICIES_DIR` | Default `policies`; ship `policy.cedar` in the image |
| `CARE_EPISODE_CLIENT_SECRET` | Required when chat proxy routes are enabled |
| Authentication registry | `chat` service entry with reachable `base_url` |
| SDK wheels | Pin `authentication-in-the-middle` and `authorization-in-the-middle` to published release URLs in production |

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| Demo session model | Accepted (v1) | `patient_uuid` doubles as episode key; full FR-004 lifecycle deferred |
| Rate limit storage in-memory | Accepted (baseline) | Set `RATE_LIMIT_STORAGE_URI` to Redis when running multiple replicas |
| Mesh clients in-repo | Accepted (v1) | `src/clients/*` local until SDK extraction |

---

## References

- [CDP Platform Security](https://github.com/Neosofia/cdp/blob/main/SECURITY.md)
- [Neosofia Service Security Baseline](https://github.com/Neosofia/templates/blob/main/python/service/SECURITY.md)
- [Constitution](https://github.com/Neosofia/cdp/blob/main/architecture/constitution.md)
- [Feature spec](https://github.com/Neosofia/cdp/blob/main/specs/015-care-episode-service.md)
