# Changelog

What changed for care-episode consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.3.0] - 2026-06-10

### Changed

- Cedar catalog reads use **`care-episode:list`**; removed `src/bootstrap/capabilities.py` and `_READ`/`_WRITE` decorator bundles.
- `@with_security` routes use REST inference or inline `action='Action::"…"'` only.
- Pinned **`authorization-in-the-middle/v0.4.23`**.
