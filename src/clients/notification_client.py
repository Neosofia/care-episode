from __future__ import annotations

from typing import Any

import httpx
from werkzeug.exceptions import BadGateway

from src.bootstrap.config import settings
from src.clients.auth_client import issue_service_token
from src.clients.service_registry_client import resolve_service_base_url

NOTIFICATION_SERVICE_SLUG = "notification"


def submit_clinical_escalation(payload: dict[str, Any]) -> None:
    """Hand off a high-risk patient turn to the notification service (internal API)."""
    try:
        base = resolve_service_base_url(NOTIFICATION_SERVICE_SLUG).rstrip("/")
    except Exception as exc:
        raise BadGateway("notification service is not available") from exc

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {issue_service_token(audience=NOTIFICATION_SERVICE_SLUG)}",
    }
    try:
        response = httpx.post(
            f"{base}/api/v1/escalations",
            headers=headers,
            json=payload,
            timeout=settings.notification_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway("notification service is temporarily unavailable") from exc

    if not response.is_success:
        raise BadGateway("notification service rejected escalation event")
