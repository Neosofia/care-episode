from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.clients import notification_client

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
INTERACTION = "00000000-0000-7000-8000-000000000002"
TENANT = "00000000-0000-7000-8000-000000000010"
MESSAGE = "00000000-0000-7000-8000-000000000003"


def _submit(**overrides):
    payload = {
        "patient_display_code": "PT-001",
        "patient_display_name": "Alex Patient",
        "procedure_name": "Knee scope",
        "days_post_op": 5,
        "care_summary": "Patient reports crushing chest pain on day 2 post-op.",
        "patient_uuid": PATIENT,
        "tenant_uuid": TENANT,
        "chat_interaction_uuid": INTERACTION,
        "message_uuid": MESSAGE,
    }
    payload.update(overrides)
    notification_client.submit_clinical_escalation(**payload)


@patch("src.clients.notification_client.resolve_service_base_url")
def test_submit_clinical_escalation_requires_registry_lookup(mock_resolve):
    mock_resolve.side_effect = ServiceUnavailable("failed to resolve service base url")
    with pytest.raises(BadGateway, match="notification service is not available"):
        _submit()


@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.httpx.post")
def test_submit_clinical_escalation_posts_email_alert(mock_post, _mock_resolve):
    response = MagicMock()
    response.is_success = True
    mock_post.return_value = response

    _submit()

    mock_post.assert_called_once()
    call = mock_post.call_args
    assert call.args[0] == "http://notification:8016/api/emails"
    assert call.kwargs["headers"] == {"Content-Type": "application/json"}
    body = call.kwargs["json"]
    assert body["from_email"] == "care-episode-alerts@neosofia.tech"
    assert body["subject"] == "Clinical risk alert — PT-001"
    assert "PT-001 (Alex Patient)" in body["message"]
    assert "Knee scope (day 5 post-op)" in body["message"]
    assert "Patient reports crushing chest pain" in body["message"]
    assert PATIENT in body["message"]


@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.httpx.post")
def test_submit_clinical_escalation_upstream_502(mock_post, _mock_resolve):
    response = MagicMock()
    response.is_success = False
    response.status_code = 502
    response.reason_phrase = "Bad Gateway"
    response.text = ""
    response.json.side_effect = ValueError("not json")
    mock_post.return_value = response

    with pytest.raises(BadGateway, match="temporarily unavailable"):
        _submit()


@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.httpx.post")
def test_submit_clinical_escalation_network_error(mock_post, _mock_resolve):
    mock_post.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(BadGateway, match="temporarily unavailable"):
        _submit()
