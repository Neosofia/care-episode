from unittest.mock import MagicMock, patch

import pytest

from src.models.care_episode import CareEpisode
from src.services.async_risk_evaluation import (
    _run_risk_evaluation,
    schedule_risk_evaluation_after_chat,
)

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
EPISODE = "00000000-0000-7000-8000-000000000099"
INTERACTION = "00000000-0000-7000-8000-000000000002"
MESSAGE = "00000000-0000-7000-8000-000000000003"


@patch("src.services.async_risk_evaluation._risk_executor")
def test_schedule_risk_evaluation_submits_background_job(mock_executor):
    pool = MagicMock()
    mock_executor.return_value = pool

    schedule_risk_evaluation_after_chat(
        patient_uuid=PATIENT,
        episode_uuid=EPISODE,
        chat_interaction_uuid=INTERACTION,
        message_uuid=MESSAGE,
        patient_message="I feel dizzy",
        tenant_uuid="00000000-0000-7000-8000-000000000010",
        patient_display_name="Alex Patient",
    )

    pool.submit.assert_called_once()
    assert pool.submit.call_args.args[0].__name__ == "_run_risk_evaluation"


@patch("src.services.async_risk_evaluation.update_risk_after_patient_chat_message")
@patch("src.services.async_risk_evaluation.get_episode_row")
@patch("src.services.async_risk_evaluation.SessionLocal")
def test_run_risk_evaluation_uses_fresh_db_session(
    mock_session_local,
    mock_get_episode,
    mock_update_risk,
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db
    episode = MagicMock(spec=CareEpisode)
    episode.patient_uuid = PATIENT
    episode.status = "active"
    mock_get_episode.return_value = episode

    _run_risk_evaluation(
        PATIENT,
        EPISODE,
        INTERACTION,
        MESSAGE,
        "I feel dizzy",
        "00000000-0000-7000-8000-000000000010",
        "Alex Patient",
    )

    mock_update_risk.assert_called_once()
    assert mock_update_risk.call_args.kwargs["patient_message"] == "I feel dizzy"


@patch("src.services.async_risk_evaluation.log_event")
@patch("src.services.async_risk_evaluation.get_episode_row", return_value=None)
@patch("src.services.async_risk_evaluation.SessionLocal")
def test_run_risk_evaluation_skips_missing_episode(
    mock_session_local,
    _mock_get_episode,
    mock_log_event,
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    _run_risk_evaluation(PATIENT, EPISODE, INTERACTION, MESSAGE, "hello", None, None)

    mock_log_event.assert_called_once()
    assert mock_log_event.call_args.args[0] == "risk_evaluation.background_skipped"


@patch("src.services.async_risk_evaluation.update_risk_after_patient_chat_message")
@patch("src.services.async_risk_evaluation.log_event")
@patch("src.services.async_risk_evaluation.get_episode_row")
@patch("src.services.async_risk_evaluation.SessionLocal")
def test_run_risk_evaluation_skips_inactive_episode(
    mock_session_local,
    mock_get_episode,
    mock_log_event,
    mock_update_risk,
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db
    episode = MagicMock(spec=CareEpisode)
    episode.patient_uuid = PATIENT
    episode.status = "closed"
    mock_get_episode.return_value = episode

    _run_risk_evaluation(PATIENT, EPISODE, INTERACTION, MESSAGE, "hello", None, None)

    mock_update_risk.assert_not_called()
    assert mock_log_event.call_args.args[0] == "risk_evaluation.background_skipped"
    assert mock_log_event.call_args.kwargs["reason"] == "episode_not_active"


@patch("src.services.async_risk_evaluation.log_event")
@patch("src.services.async_risk_evaluation.get_episode_row")
@patch("src.services.async_risk_evaluation.SessionLocal")
def test_run_risk_evaluation_logs_background_failure(
    mock_session_local,
    mock_get_episode,
    mock_log_event,
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db
    mock_get_episode.side_effect = RuntimeError("db unavailable")

    _run_risk_evaluation(PATIENT, EPISODE, INTERACTION, MESSAGE, "hello", None, None)

    assert mock_log_event.call_args.args[0] == "risk_evaluation.background_failed"
