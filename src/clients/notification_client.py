from __future__ import annotations

import httpx
from platform_client import UpstreamError, UpstreamUnavailable, raise_for_upstream_response
from werkzeug.exceptions import BadGateway

from src.bootstrap.config import settings
from src.clients.mesh_client import resolve_service_base_url

NOTIFICATION_SERVICE_SLUG = "notification"


def submit_clinical_escalation(
    *,
    patient_display_code: str,
    patient_display_name: str,
    procedure_name: str,
    days_post_op: int,
    care_summary: str,
    patient_uuid: str,
    tenant_uuid: str,
    chat_interaction_uuid: str,
    message_uuid: str,
) -> None:
    """Relay a high-risk patient turn to the Neosofia inbox via notification email relay."""
    try:
        base = resolve_service_base_url(NOTIFICATION_SERVICE_SLUG).rstrip("/")
    except Exception as exc:
        raise BadGateway("notification service is not available") from exc

    patient_line = patient_display_code
    if patient_display_name.strip():
        patient_line = f"{patient_display_code} ({patient_display_name.strip()})"

    payload = {
        "from_email": settings.clinical_risk_alert_from_email,
        "subject": f"Clinical risk alert — {patient_display_code}",
        "message": (
            "Care Episode detected high clinical risk on a patient chat message.\n\n"
            f"Patient: {patient_line}\n"
            f"Procedure: {procedure_name.strip()} (day {days_post_op} post-op)\n\n"
            "Care summary:\n"
            f"{care_summary.strip()}\n\n"
            "Reference:\n"
            f"Patient UUID: {patient_uuid}\n"
            f"Tenant UUID: {tenant_uuid}\n"
            f"Chat interaction UUID: {chat_interaction_uuid}\n"
            f"Message UUID: {message_uuid}\n"
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
