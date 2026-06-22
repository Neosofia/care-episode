# Product Installation Plan

Per-version deploy steps for operators. User-visible changes: [CHANGELOG.md](CHANGELOG.md).

## care-episode v0.11.0

**Image:** `ghcr.io/neosofia/care-episode:v0.11.0` (tag `care-episode/v0.11.0`)

**Deploy:**

1. Redeploy **care-episode v0.11.0** (no new migration; head **`012`**).

**Verify:**

- `GET /health` → `"version": "0.11.0"`.
- `GET /api/v1/care-episodes/procedures` returns catalog items (clinician JWT).
- CDP enroll workflow can load procedure picker without **503**.

**Evidence:** Health JSON; `GET /procedures` response sample; enroll e2e or manual procedure picker screenshot.

---

## care-episode v0.10.0

**Image:** `ghcr.io/neosofia/care-episode:v0.10.0` (tag `care-episode/v0.10.0`)

**Build identifiers:** **`authorization-in-the-middle/v0.7.7`**; deploy **authentication v0.39.0** or later in the same window so service tokens carry `neosofia:service_uuid`.

**Deploy:**

1. Redeploy **authentication v0.39.0** (if not already on that tag).
2. Redeploy **care-episode v0.10.0** (no new migration; head **`012`**).

**Verify:**

- `GET /health` → `"version": "0.10.0"`.
- `alembic_version` is **`012`**.
- Clinician patient detail → **Audits** loads episode and rolling-risk sections; CSV export works.
- `PATCH /api/v1/care-episodes/{episode_uuid}` with `changed_by_uuid` in the body returns **400**.
- Close/reopen episode shows **User** (not **Service**) for clinician actions in audit history.

**Evidence:** Health JSON; audit UI screenshot; rejected forged attribution response.

---

## care-episode v0.9.0

**Image:** `ghcr.io/neosofia/care-episode:v0.9.0` (tag `care-episode/v0.9.0`)

**Deploy:**

1. Redeploy **care-episode v0.9.0** (no new migration; head **`012`**).
2. Redeploy **CDP UI 2026.06.21** or later in the same change window.

**Verify:**

- `GET /health` → `"version": "0.9.0"`.
- `alembic_version` is **`012`**.
- Clinician **Enroll** still creates patients and opens post-care monitoring in CDP.
- Patient chat and episode lifecycle (close, reopen, new episode) unchanged.

**Evidence:** Health JSON version field; staging E2E and visual walkthrough green.

---

## care-episode v0.8.2

**Image:** `ghcr.io/neosofia/care-episode:v0.8.2` (tag `care-episode/v0.8.2`)

**Deploy:**

1. Redeploy **care-episode v0.8.2** (no new migration; head **`012`**).
2. Set **`FRONTEND_URL`** to the CDP UI base URL (clinical risk alert deep links).
3. Redeploy **CDP UI 2026.06.20** or later in the same change window.

**Verify:**

- `GET /health` → `"version": "0.8.2"`.
- `alembic_version` is **`012`**.
- High-risk patient chat triggers a clinical alert email whose body is a deep link only (no patient names or message text).
- Patient chat greeting reflects the display name supplied by the client.

**Evidence:** Health JSON version field; staging E2E green.

---

## care-episode v0.8.1

**Image:** `ghcr.io/neosofia/care-episode:v0.8.1` (tag `care-episode/v0.8.1`)

**Deploy:**

1. Redeploy **care-episode v0.8.1** (migration **`012`**: drop denormalized patient labels from recoveries).
2. Redeploy **CDP UI 2026.06.19** or later in the same change window.

**Verify:**

- `GET /health` → `"version": "0.8.1"`.
- `alembic_version` is **`012`**.
- Episode API payloads omit `display_code` and `display_name`; roster labels come from the User registry in the UI.
- Patient chat completion still succeeds.

**Evidence:** Health JSON version field; staging E2E close/reopen for **DEMO-123**.

---

## care-episode v0.8.0

**Image:** `ghcr.io/neosofia/care-episode:v0.8.0` (tag `care-episode/v0.8.0`)

**Deploy:**

1. Redeploy **care-episode v0.8.0** (migrations **`009`**–**`011`**: multi-episode model, `care_window_days`, drop `closed_at`).
2. Redeploy **CDP UI 2026.06.18** or later in the same change window.
3. Ensure **notification** is registered when **`RISK_ESCALATION_ENABLED`** is true.

**Verify:**

- `GET /health` → `"version": "0.8.0"`.
- `alembic_version` is **`011`**.
- Clinician JWT with `neosofia:tenant_uuid` can list and patch same-tenant episodes; cross-tenant access returns **403**.
- `GET /api/v1/care-episodes/{patient_uuid}/episodes` returns history with at most one `is_current` active row.

**Evidence:** Health JSON version field; Cedar logs show matching `tenant_uuid` on catalog and member routes.

---

## care-episode v0.7.2

**Image:** `ghcr.io/neosofia/care-episode:v0.7.2` (tag `care-episode/v0.7.2`)

**Deploy:**

1. Redeploy **care-episode v0.7.2** (no new migrations).
2. Ensure **notification** is registered (`slug: notification`) when **`RISK_ESCALATION_ENABLED`** is true (default).
3. Optional: set **`CLINICAL_RISK_ALERT_FROM_EMAIL`** (default `care-episode-alerts@neosofia.tech`).

**Verify:**

- `GET /health` → `"version": "0.7.2"`.
- High-risk chat completion triggers a clinical alert email via notification when escalation is enabled.

**Evidence:** Health JSON version field; structured logs show successful chat proxy and risk evaluation outcomes.

---

## care-episode v0.7.1

**Image:** `ghcr.io/neosofia/care-episode:v0.7.1` (tag `care-episode/v0.7.1`)

**Deploy:**

1. Redeploy **care-episode v0.7.1** (no new migrations or env vars).

**Verify:**

- `GET /health` → `"version": "0.7.1"`.
- Demo workspace bootstrap completes `POST /api/v1/care-episodes` for the signed-in demo user (201, not 403).

**Evidence:** Health JSON version field; demo bootstrap recovery create succeeds on staging.

---

## care-episode v0.7.0

**Image:** `ghcr.io/neosofia/care-episode:v0.7.0` (tag `care-episode/v0.7.0`)

**Deploy:**

1. Redeploy **care-episode v0.7.0** (SDK **`authorization-in-the-middle/v0.7.1`** only; no new migrations).

**Verify:**

- `GET /health` → `"version": "0.7.0"`.
- Chat proxy interaction create and completion proxy smoke checks pass.

**Evidence:** Health JSON version field; structured logs show successful chat proxy outcomes.

---

## care-episode v0.6.0

**Image:** `ghcr.io/neosofia/care-episode:v0.6.0` (tag `care-episode/v0.6.0`)

**Deploy:**

1. Redeploy **care-episode v0.6.0** (migration **`008`** — `interaction_risk_states`; risk level on recoveries).
2. Set **`INFERENCE_COMPLETIONS_URL`**, **`INFERENCE_API_KEY`**, and **`INFERENCE_MODEL`** for clinical risk evaluation.
3. Keep **`CARE_EPISODE_CLIENT_SECRET`** and Chat registry entry from prior releases.
4. Optional: set **`RISK_ESCALATION_ENABLED=false`** to disable high-risk email alerts.

**Verify:**

- `GET /health` → `"version": "0.6.0"**.
- Patient content completion → **200** with Chat reply and `risk_evaluation` object.
- `session_start` completion → **200** without `risk_evaluation`.
- With inference env unset, content completion → `risk_evaluation.risk_level` is `failed-pending-review`.

**Evidence:** Health JSON version field; migration **`008`** applied.

---

## care-episode v0.5.0

**Image:** `ghcr.io/neosofia/care-episode:v0.5.0` (tag `care-episode/v0.5.0`)

**Deploy:**

1. Deploy **chat v0.5.0** in the same change window.
2. Set **`CARE_EPISODE_CLIENT_SECRET`** (client credentials for care-episode → authentication token exchange).
3. Ensure **Chat** is registered in the authentication service registry (`slug: chat`).
4. Run migration **`006`** if upgrading from v0.4.0.

**Verify:**

- `GET /health` → `"version": "0.5.0"`.
- Chat interaction create and completion proxy smoke checks pass.

---

## care-episode v0.3.0

**Image:** `ghcr.io/neosofia/care-episode:v0.3.0` (tag `care-episode/v0.3.0`)

**Deploy:**

1. Redeploy **care-episode v0.3.0** (SDK **`authorization-in-the-middle/v0.4.23`** baked into the image; no new migrations).

**Verify:**

- `GET /health` → `"version": "0.3.0"`.
- Recovery list and invite smoke checks pass.
