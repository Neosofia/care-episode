from __future__ import annotations

from logenvelope.flask import log_request_handled as _log_request_handled


def log_request_handled(operation: str, status_code: int, **extra) -> None:
    """Care Episode OR-001 telemetry — PHI-safe request outcome events."""
    _log_request_handled(operation, status_code, **extra)
