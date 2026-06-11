import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g
from werkzeug.exceptions import NotFound

from src.models.care_episode import CareEpisodeSession
from src.services.chat_proxy_service import create_chat_interaction, proxy_chat_completion, require_session

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
INTERACTION = "00000000-0000-7000-8000-000000000002"


def _session_row() -> CareEpisodeSession:
    import datetime

    return CareEpisodeSession(
        patient_uuid=uuid.UUID(PATIENT),
        display_code="PT-001",
        display_name="Alex Patient",
        surgery="Knee scope",
        procedure_date=datetime.date.today(),
        session_id="sess-1",
        risk_level="low",
        tenant_uuid=uuid.UUID("00000000-0000-7000-8000-000000000010"),
        changed_by_uuid=uuid.UUID("00000000-0000-7000-8000-000000000000"),
        changed_by_type=2,
    )


def test_require_session_not_found():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(NotFound):
        require_session(db, PATIENT)


@patch("src.services.chat_proxy_service.chat_client.create_interaction")
def test_create_chat_interaction(mock_create):
    db = MagicMock()
    db.get.return_value = _session_row()
    mock_create.return_value = {"chat_interaction_uuid": INTERACTION, "user_uuid": PATIENT}
    result = create_chat_interaction(db, PATIENT)
    assert result["chat_interaction_uuid"] == INTERACTION
    assert result["care_episode_uuid"] == PATIENT
    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert args[0] == PATIENT
    assert kwargs["context"]["procedure_name"] == "Knee scope"
    assert kwargs["context"]["tenant_uuid"] == str(_session_row().tenant_uuid)


@patch("src.services.chat_proxy_service.chat_client.create_interaction")
def test_create_chat_interaction_prefers_jwt_tenant(mock_create):
    app = Flask(__name__)
    jwt_tenant = "00000000-0000-7000-8000-000000000099"
    db = MagicMock()
    db.get.return_value = _session_row()
    mock_create.return_value = {"chat_interaction_uuid": INTERACTION, "user_uuid": PATIENT}
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": PATIENT,
            "neosofia:tenant_uuid": jwt_tenant,
        }
        create_chat_interaction(db, PATIENT)
    assert mock_create.call_args.kwargs["context"]["tenant_uuid"] == jwt_tenant


@patch("src.services.chat_proxy_service.chat_client.create_completion")
def test_proxy_chat_completion_updates_last_activity(mock_create):
    db = MagicMock()
    session = _session_row()
    db.get.return_value = session
    mock_create.return_value = {"message": "hello"}
    result = proxy_chat_completion(
        db,
        PATIENT,
        INTERACTION,
        {"content": "Hi"},
    )
    assert result["message"] == "hello"
    mock_create.assert_called_once_with(PATIENT, INTERACTION, {"content": "Hi"})
    assert session.last_activity
    db.commit.assert_called_once()
