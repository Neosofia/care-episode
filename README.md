# Care Episode Service

Authoritative store for **procedure-scoped post-discharge care episodes** on the platform. Each episode groups a patient, procedure reference, care window, invite linkage, and lifecycle status so clinician and patient experiences can answer which recovery window applies without mixing separate procedures for the same person.

The CDP clinician and patient apps call this service for active session summaries, demo enrichment (records, appointments, inbox), and post-care invite flows. Authentication establishes identity; the User Service holds platform roles; the Chat Service stores conversations by user and interaction. This service owns episode-shaped clinical context and dashboard data that product UIs compose alongside chat — not message transcripts themselves. Downstream lifecycle subscribers receive identifier-only events when episodes open or close.

## Resources

### Operations

For testers, developers, and system administrators, [OPERATIONS.md](OPERATIONS.md) covers local setup, migrations, ports, and smoke checks. Per-release operator steps and verification are in [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

### Changelog

For operators, integrators, and product owners, [CHANGELOG.md](CHANGELOG.md) records user-visible changes per release ([Keep a Changelog](https://keepachangelog.com/)).

### API Contract

For API consumers, integration testers, and frontend developers, [openapi.json](openapi.json) is the authoritative machine-readable contract for this service. It is maintained in-repo for CI and codegen; it is **not** served over HTTP in any environment.

### Security Policy

For security reviewers, on-call engineers, and contributors, [SECURITY.md](SECURITY.md) documents the threat model, authz boundaries, and logging rules for this service.

### Feature Specification

For product owners, architects, and new contributors, the [feature spec](https://github.com/Neosofia/cdp/blob/main/specs/015-care-episode-service.md) describes goals, functional requirements, and acceptance criteria. It is the binding record of what the component must do.
