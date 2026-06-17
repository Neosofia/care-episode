from __future__ import annotations

import httpx
from platform_client import UpstreamError, UpstreamUnavailable, raise_for_upstream_response
from werkzeug.exceptions import BadGateway

from src.bootstrap.config import settings
from src.clients.mesh_client import resolve_service_base_url

NOTIFICATION_SERVICE_SLUG = "notification"


def _patient_record_url(*, patient_uuid: str, episode_uuid: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/clinician/patients/{patient_uuid}?episode_uuid={episode_uuid}"


def submit_clinical_escalation(
    *,
    patient_uuid: str,
    episode_uuid: str,
    tenant_uuid: str,
    chat_interaction_uuid: str,
    message_uuid: str,
) -> None:
    """Relay a high-risk alert with a deep link only — no PHI/PII in email body."""
    try:
        base = resolve_service_base_url(NOTIFICATION_SERVICE_SLUG).rstrip("/")
    except Exception as exc:
        raise BadGateway("notification service is not available") from exc

    record_url = _patient_record_url(patient_uuid=patient_uuid, episode_uuid=episode_uuid)
    payload = {
        "from_email": settings.clinical_risk_alert_from_email,
        "subject": "Clinical risk alert",
        "message": (
            "A patient chat message was flagged as high clinical risk.\n\n"
            "Open the patient record in Neosofia:\n"
            f"{record_url}\n"
        ),
    }

    try:
        response = httpx.post(
            f"{base}/api/emails",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=settings.notification_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway("notification service is temporarily unavailable") from exc

    try:
        raise_for_upstream_response(response)
    except UpstreamUnavailable as exc:
        raise BadGateway("notification service is temporarily unavailable") from exc
    except UpstreamError as exc:
        raise BadGateway("notification service rejected clinical risk alert") from exc
