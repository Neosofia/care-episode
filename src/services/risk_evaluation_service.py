from __future__ import annotations

import uuid
from typing import Any

from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.bootstrap.config import settings
from src.bootstrap.request_telemetry import log_request_handled
from src.clients import notification_client
from src.models.care_episode import CareEpisode
from src.models.risk import InteractionRiskState
from src.services.chat_context import build_interaction_context, days_post_op_for
from src.services.inference_health import risk_inference_configured
from src.services.risk_agent_service import RiskAgent

SYSTEM_ACTOR_UUID = uuid.UUID("00000000-0000-7000-8000-000000000000")
SERVICE_ACTOR_TYPE = 2

# API status when inference cannot run. care_episode_recoveries.risk_level is not changed.
RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE = "failed-pending-review"


def _stamp_system_service_actor_on_row(
    audited_database_row: CareEpisode | InteractionRiskState,
) -> None:
    audited_database_row.changed_by_uuid = SYSTEM_ACTOR_UUID
    audited_database_row.changed_by_type = SERVICE_ACTOR_TYPE


def _load_or_create_interaction_risk_summary_row(
    db,
    chat_interaction_uuid: uuid.UUID,
    patient_uuid: uuid.UUID,
) -> InteractionRiskState:
    interaction_risk_summary = db.get(InteractionRiskState, chat_interaction_uuid)
    if interaction_risk_summary is not None:
        return interaction_risk_summary

    interaction_risk_summary = InteractionRiskState(
        chat_interaction_uuid=chat_interaction_uuid,
        patient_uuid=patient_uuid,
        summary="",
        changed_by_uuid=SYSTEM_ACTOR_UUID,
        changed_by_type=SERVICE_ACTOR_TYPE,
    )
    db.add(interaction_risk_summary)
    db.flush()
    return interaction_risk_summary


def _build_risk_evaluation_response(
    reported_risk_level: str,
    *,
    clinician_escalation_submitted: bool,
) -> dict[str, Any]:
    return {
        "risk_level": reported_risk_level,
        "escalated": clinician_escalation_submitted,
    }


def _submit_high_risk_escalation_to_notification(
    episode: CareEpisode,
    *,
    chat_interaction_uuid: uuid.UUID,
    tenant_uuid: uuid.UUID,
    chat_message_uuid: uuid.UUID,
) -> bool:
    if not settings.risk_escalation_enabled:
        return False

    try:
        notification_client.submit_clinical_escalation(
            patient_uuid=str(episode.patient_uuid),
            episode_uuid=str(episode.episode_uuid),
            tenant_uuid=str(tenant_uuid),
            chat_interaction_uuid=str(chat_interaction_uuid),
            message_uuid=str(chat_message_uuid),
        )
    except BadGateway:
        log_request_handled("risk_escalation", 502, outcome="notification_downstream")
        return False

    log_request_handled("risk_escalation", 200, outcome="submitted")
    return True


def update_risk_after_patient_chat_message(
    db,
    *,
    episode: CareEpisode,
    chat_interaction_uuid: str,
    message_uuid: str,
    patient_message: str,
    tenant_uuid: str | None = None,
    patient_display_name: str | None = None,
) -> dict[str, Any]:
    """Score one patient chat turn: refresh interaction summary and episode risk level."""
    chat_message_uuid = uuid.UUID(str(message_uuid))
    parsed_chat_interaction_uuid = uuid.UUID(str(chat_interaction_uuid))
    parsed_tenant_uuid = uuid.UUID(str(tenant_uuid or episode.tenant_uuid))

    if not risk_inference_configured():
        log_request_handled(
            "risk_evaluation",
            503,
            outcome=RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
        )
        return _build_risk_evaluation_response(
            RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
            clinician_escalation_submitted=False,
        )

    interaction_risk_summary = _load_or_create_interaction_risk_summary_row(
        db,
        parsed_chat_interaction_uuid,
        episode.patient_uuid,
    )

    risk_agent_episode_context = build_interaction_context(
        episode,
        tenant_uuid=str(parsed_tenant_uuid),
        patient_display_name=patient_display_name,
    )
    risk_agent_episode_context["current_risk_level"] = episode.risk_level or "low"

    try:
        risk_agent_result = RiskAgent.evaluate(
            episode_context=risk_agent_episode_context,
            prior_summary=interaction_risk_summary.summary,
            patient_message=patient_message,
        )
    except ServiceUnavailable:
        log_request_handled(
            "risk_evaluation",
            503,
            outcome=RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
        )
        return _build_risk_evaluation_response(
            RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
            clinician_escalation_submitted=False,
        )

    interaction_risk_summary.summary = risk_agent_result.summary
    _stamp_system_service_actor_on_row(interaction_risk_summary)
    episode.risk_level = risk_agent_result.risk_level
    _stamp_system_service_actor_on_row(episode)

    clinician_escalation_submitted = False
    if risk_agent_result.risk_level == "high":
        clinician_escalation_submitted = _submit_high_risk_escalation_to_notification(
            episode,
            chat_interaction_uuid=parsed_chat_interaction_uuid,
            tenant_uuid=parsed_tenant_uuid,
            chat_message_uuid=chat_message_uuid,
        )

    db.commit()
    log_request_handled(
        "risk_evaluation",
        200,
        outcome=risk_agent_result.risk_level,
        escalated=clinician_escalation_submitted,
    )
    return _build_risk_evaluation_response(
        risk_agent_result.risk_level,
        clinician_escalation_submitted=clinician_escalation_submitted,
    )
