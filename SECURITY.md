# Neosofia Service Security Baseline

This document defines the security posture pre-wired into the Python service template. It applies as a baseline to **every web service** in the Neosofia platform. Each instantiated service should maintain its own `SECURITY.md` that references these baselines and adds controls, threat models, and known gaps unique to that service.

To report any security-related issue please email security@neosofia.tech — do not create a public issue.

---

## 1. Standards & Frameworks

Every service is designed and audited against:

| Domain | Standard / Framework |
|---|---|
| **Web Application Security** | [OWASP Top 10 (2021)](https://owasp.org/Top10/), [OWASP ASVS Level 2](https://owasp.org/www-project-application-security-verification-standard/), [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) |
| **Healthcare Compliance** | [HIPAA Security Rule §164.312](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C/section-164.312) (audit, integrity, transmission security); no PHI in logs per Constitution §I |
| **Transport Security** | [TLS 1.2+](https://datatracker.ietf.org/doc/html/rfc5246) enforced at ingress; [HSTS](https://datatracker.ietf.org/doc/html/rfc6797) (1 year, includeSubDomains) |
| **Internal Governance** | [Constitution §I](https://github.com/Neosofia/cdp/blob/main/architecture/constitution.md) (no PHI/PII in logs), §VIII (defense in depth) |
| **SDLC** | [Neosofia SDLC Security Checklist](https://neosofia.tech/resources/checklists/sdlc/) |

---

## 2. Baseline Security Controls

The following controls are required for every Neosofia web service. Deviations must be documented with a rationale in the service's own `SECURITY.md`.

### Transport Security

TLS is terminated at the ingress layer (Traefik in dev/staging; platform ingress in production). In-service traffic travels over HTTP within an isolated private network segment, consistent with HIPAA §164.312(e)(1). Environments requiring in-transit encryption for all hops (PCI-DSS v4, FedRAMP High) would require mutual TLS between containers.

`flask-talisman` enforces HTTPS and emits the following headers in production on every response:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Proxy Trust

`werkzeug.middleware.proxy_fix.ProxyFix` is configured with an explicit, configurable hop count (`TRUSTED_PROXY_HOPS` env var, default `1`). Setting it to `0` disables forwarded-header trust entirely. This prevents IP spoofing via crafted `X-Forwarded-For` headers.

### Authentication & Authorization

- **Authentication**: Strict JWT validation relying on dynamically provisioned cryptographic keys.
- **Authorization**: Fail-closed, in-process Cedar evaluation.
- Requests exceeding the max payload cap are rejected to prevent resource starvation.
- Generic JSON error payloads are returned for invalid requests, missing resources, and authorization failures to prevent data leakage.

### Rate Limiting

All API endpoints are rate-limited via `flask-limiter`. Rate limit state defaults to in-memory storage; multi-replica deployments must set `RATE_LIMIT_STORAGE_URI` to a Redis URL for accurate cross-worker limiting. The service logs a warning at startup if in-memory storage is used with more than one worker in a production environment.

### Logging & Observability

Structured JSON logs are emitted via `logenvelope`, validated against [schemas/log.json](https://github.com/Neosofia/schemas/blob/main/log-v1.0.0.json). 
- No PHI, PII, or SPII appears in any log line (Constitution §I). 
- Exception types are logged as `type(exc).__name__` — never `str(exc)`.
- Machine-readable event names are used for lifecycle and error events.

### Secrets & Configuration

All secrets are injected via environment variables. No secrets are hard-coded or committed to version control. Settings are validated at startup with a typed Pydantic model — the service fails loudly before accepting traffic if required configuration is absent or malformed.

### Container Hardening

- Base image pinned to a SHA-256 digest (not a mutable tag).
- Multi-stage build; build tools are absent from the final image.
- Process runs as a non-root `app` user.
- `HEALTHCHECK` instruction present for orchestrator liveness detection.
- `PYTHONUNBUFFERED=1` ensures logs reach stdout without buffering.
- Lockfile (`uv.lock`) copied into the image; installed with `uv sync --frozen` for reproducible, hash-verified builds.

### Dependency Management

- `uv.lock` is committed and pinned to exact versions with hashes.
- Dev dependencies are separated from runtime dependencies.
- Trivy scans the lockfile and the built image on every CI run (CRITICAL/HIGH severity threshold; build fails on findings).

### CI / CD

Every service uses the central reusable workflows from `Neosofia/platform-workflows`:
- `_test-python.yml` — pytest with an 80% coverage gate.
- `_scan.yml` — Trivy vulnerability and secret scan of lockfile + Docker image.
Deployment to GHCR is gated on both workflows passing.

---

## 3. Template Deployment Notes

- **SDK Artifacts**: Ensure the `authentication-in-the-middle` and `authorization-in-the-middle` dependencies pull from your firm's immutable git tags or PyPI registry releases when instantiating this template.
- **Caching**: Ensure you pivot rate limit tracking from Memory to Redis for proper distributed environments.
