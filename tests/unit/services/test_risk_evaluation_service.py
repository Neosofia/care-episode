import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.models.care_episode import CareEpisodeRecovery
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


def _recovery() -> CareEpisodeRecovery:
    return CareEpisodeRecovery(
        patient_uuid=PATIENT,
        display_code="PT-001",
        display_name="Alex Patient",
        surgery="Knee scope",
        procedure_date=__import__("datetime").date.today(),
        recovery_id="rec-1",
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
        recovery=_recovery(),
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
def test_update_risk_after_patient_chat_message_updates_recovery_and_escalates(
    mock_configured,
    mock_evaluate,
    mock_escalate,
):
    db = MagicMock()
    db.get.return_value = None

    recovery = _recovery()
    result = update_risk_after_patient_chat_message(
        db,
        recovery=recovery,
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="crushing chest pain",
    )

    assert result == {"risk_level": "high", "escalated": True}
    assert recovery.risk_level == "high"
    mock_escalate.assert_called_once()
    db.commit.assert_called_once()


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
        recovery=_recovery(),
        chat_interaction_uuid=str(INTERACTION),
        message_uuid=str(MESSAGE),
        patient_message="feeling better",
    )

    assert interaction_risk_summary.summary == "Stable recovery check-in."
