import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.models.care_episode import CareEpisode
from src.models.risk import InteractionRiskState
from src.services.risk_agent_service import RiskAgentResult
from src.services.risk_evaluation_service import (
    RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
    update_risk_after_patient_chat_message,
)

pytestmark = pytest.mark.unit

PATIENT = uuid.UUID("00000000-0000-7000-8000-000000000001")
INTERACTION = uuid.UUID("00000000-0000-7000-8000-000000000002")
MESSAGE = uuid.UUID("00000000-0000-7000-8000-000000000003")
TENANT = uuid.UUID("00000000-0000-7000-8000-000000000010")
EPISODE = uuid.UUID("00000000-0000-7000-8000-000000000099")


def _episode() -> CareEpisode:
    return CareEpisode(
        episode_uuid=EPISODE,
        patient_uuid=PATIENT,
        surgery="Knee scope",
        procedure_date=__import__("datetime").date.today(),
        recovery_id="rec-1",
        last_activity="2026-06-01T12:00:00Z",
        risk_level="low",
        tenant_uuid=TENANT,
        changed_by_uuid=uuid.UUID("00000000-0000-7000-8000-000000000000"),
        changed_by_type=2,
    )


@patch("src.services.risk_evaluation_service.risk_inference_configured", return_value=False)
def test_update_risk_after_patient_chat_message_when_inference_unconfigured(mock_configured):
    db = MagicMock()

    result = update_risk_after_patient_chat_message(
        db,
        episode=_episode(),
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="I feel dizzy",
    )

    assert result == {
        "risk_level": RISK_LEVEL_WHEN_INFERENCE_UNAVAILABLE,
        "escalated": False,
    }
    db.commit.assert_not_called()
    db.add.assert_not_called()


@patch(
    "src.services.risk_evaluation_service._submit_high_risk_escalation_to_notification",
    return_value=True,
)
@patch(
    "src.services.risk_evaluation_service.RiskAgent.evaluate",
    return_value=RiskAgentResult(
        risk_level="high",
        summary="Patient reports crushing chest pain on day 2 post-op.",
    ),
)
@patch("src.services.risk_evaluation_service.risk_inference_configured", return_value=True)
def test_update_risk_after_patient_chat_message_updates_episode_and_escalates(
    mock_configured,
    mock_evaluate,
    mock_escalate,
):
    db = MagicMock()
    db.get.return_value = None

    episode = _episode()
    result = update_risk_after_patient_chat_message(
        db,
        episode=episode,
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="crushing chest pain",
        patient_display_name="Alex Patient",
    )

    assert result == {"risk_level": "high", "escalated": True}
    assert episode.risk_level == "high"
    mock_escalate.assert_called_once_with(
        episode,
        chat_interaction_uuid=INTERACTION,
        tenant_uuid=TENANT,
        chat_message_uuid=MESSAGE,
    )
    db.commit.assert_called_once()


@patch("src.services.risk_evaluation_service.log_event")
@patch("src.services.risk_evaluation_service.notification_client.submit_clinical_escalation")
@patch(
    "src.services.risk_evaluation_service.RiskAgent.evaluate",
    return_value=RiskAgentResult(
        risk_level="high",
        summary="Patient reports crushing chest pain on day 2 post-op.",
    ),
)
@patch("src.services.risk_evaluation_service.risk_inference_configured", return_value=True)
def test_update_risk_after_patient_chat_message_escalation_sends_deep_link_only(
    mock_configured,
    mock_evaluate,
    mock_submit,
    mock_log_event,
):
    db = MagicMock()
    db.get.return_value = None
    mock_submit.return_value = None

    update_risk_after_patient_chat_message(
        db,
        episode=_episode(),
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="crushing chest pain",
    )

    mock_submit.assert_called_once_with(
        patient_uuid=str(PATIENT),
        episode_uuid=str(EPISODE),
        tenant_uuid=str(TENANT),
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
    )
    mock_log_event.assert_called_once_with(
        "clinical_escalation.submitted",
        episode_uuid=str(EPISODE),
        chat_interaction_uuid=str(INTERACTION),
        chat_message_uuid=str(MESSAGE),
        tenant_uuid=str(TENANT),
    )


@patch(
    "src.services.risk_evaluation_service.RiskAgent.evaluate",
    return_value=RiskAgentResult(risk_level="low", summary="Stable recovery check-in."),
)
@patch("src.services.risk_evaluation_service.risk_inference_configured", return_value=True)
def test_update_risk_after_patient_chat_message_updates_interaction_summary(
    mock_configured,
    mock_evaluate,
):
    db = MagicMock()
    interaction_risk_summary = InteractionRiskState(
        chat_interaction_uuid=INTERACTION,
        patient_uuid=PATIENT,
        summary="old",
        changed_by_uuid=uuid.UUID("00000000-0000-7000-8000-000000000000"),
        changed_by_type=2,
    )
    db.get.return_value = interaction_risk_summary

    update_risk_after_patient_chat_message(
        db,
        episode=_episode(),
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="feeling better",
        patient_display_name="Alex Patient",
    )

    assert interaction_risk_summary.summary == "Stable recovery check-in."
