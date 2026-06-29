import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g
from werkzeug.exceptions import NotFound

from src.models.care_episode import CareEpisode
from src.services.chat_proxy_service import (
    create_chat_interaction,
    proxy_chat_completion,
    require_episode,
)

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
EPISODE = "00000000-0000-7000-8000-000000000099"
INTERACTION = "00000000-0000-7000-8000-000000000002"


def _episode_row() -> CareEpisode:
    import datetime

    return CareEpisode(
        episode_uuid=uuid.UUID(EPISODE),
        patient_uuid=uuid.UUID(PATIENT),
        surgery="Knee scope",
        procedure_date=datetime.date.today(),
        recovery_id="sess-1",
        last_activity="2026-06-01T12:00:00Z",
        risk_level="low",
        status="active",
        tenant_uuid=uuid.UUID("00000000-0000-7000-8000-000000000010"),
        changed_by_uuid=uuid.UUID("00000000-0000-7000-8000-000000000000"),
        changed_by_type=2,
    )


@patch("src.services.chat_proxy_service.get_active_episode", return_value=None)
def test_require_episode_not_found(_mock_active):
    db = MagicMock()
    with pytest.raises(NotFound):
        require_episode(db, PATIENT)


@patch("src.services.chat_proxy_service.get_active_episode")
@patch("src.services.chat_proxy_service.chat_client.create_interaction")
def test_create_chat_interaction(mock_create, mock_active):
    episode = _episode_row()
    db = MagicMock()
    mock_active.return_value = episode
    mock_create.return_value = {"chat_interaction_uuid": INTERACTION, "user_uuid": PATIENT}
    result = create_chat_interaction(
        db,
        PATIENT,
        {"patient_display_name": "Alex Patient"},
    )
    assert result["chat_interaction_uuid"] == INTERACTION
    assert result["care_episode_uuid"] == EPISODE
    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["context"]["procedure_name"] == "Knee scope"
    assert kwargs["context"]["patient_display_name"] == "Alex Patient"
    assert kwargs["context"]["tenant_uuid"] == str(episode.tenant_uuid)


@patch("src.services.chat_proxy_service.get_active_episode")
@patch("src.services.chat_proxy_service.chat_client.create_interaction")
def test_create_chat_interaction_prefers_jwt_tenant(mock_create, mock_active):
    app = Flask(__name__)
    jwt_tenant = "00000000-0000-7000-8000-000000000099"
    db = MagicMock()
    mock_active.return_value = _episode_row()
    mock_create.return_value = {"chat_interaction_uuid": INTERACTION, "user_uuid": PATIENT}
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": PATIENT,
            "neosofia:tenant_uuid": jwt_tenant,
        }
        create_chat_interaction(db, PATIENT, {"patient_display_name": "Alex Patient"})
    assert mock_create.call_args.kwargs["context"]["tenant_uuid"] == jwt_tenant


@patch("src.services.chat_proxy_service.get_active_episode")
@patch("src.services.chat_proxy_service.schedule_risk_evaluation_after_chat")
@patch("src.services.chat_proxy_service.chat_client.create_completion")
def test_proxy_chat_completion_updates_last_activity(mock_create, mock_schedule, mock_active):
    db = MagicMock()
    episode = _episode_row()
    mock_active.return_value = episode
    mock_create.return_value = {
        "message": "hello",
        "user_message": {"message_uuid": "00000000-0000-7000-8000-000000000099"},
    }
    app = Flask(__name__)
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": PATIENT,
            "neosofia:token_type": "human",
        }
        result = proxy_chat_completion(
            db,
            PATIENT,
            INTERACTION,
            {"content": "Hi", "patient_display_name": "Alex Patient"},
        )
    assert result["message"] == "hello"
    assert "risk_evaluation" not in result
    mock_schedule.assert_called_once()
    assert mock_schedule.call_args.kwargs["patient_display_name"] == "Alex Patient"
    assert episode.last_activity
    db.commit.assert_called_once()


@patch("src.services.chat_proxy_service.get_active_episode")
@patch("src.services.chat_proxy_service.schedule_risk_evaluation_after_chat")
@patch("src.services.chat_proxy_service.chat_client.create_completion")
def test_proxy_chat_completion_skips_risk_on_session_start(mock_create, mock_schedule, mock_active):
    db = MagicMock()
    mock_active.return_value = _episode_row()
    mock_create.return_value = {"message": "Welcome", "assistant_message": {"message_uuid": "a1"}}
    app = Flask(__name__)
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": PATIENT,
            "neosofia:token_type": "human",
        }
        result = proxy_chat_completion(
            db,
            PATIENT,
            INTERACTION,
            {"session_start": True},
        )
    assert "risk_evaluation" not in result
    mock_schedule.assert_not_called()
