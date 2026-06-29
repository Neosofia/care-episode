from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.clients import notification_client

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
EPISODE = "00000000-0000-7000-8000-000000000099"
INTERACTION = "00000000-0000-7000-8000-000000000002"
TENANT = "00000000-0000-7000-8000-000000000010"
MESSAGE = "00000000-0000-7000-8000-000000000003"


def _submit(**overrides):
    payload = {
        "patient_uuid": PATIENT,
        "episode_uuid": EPISODE,
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


@patch("src.clients.notification_client.settings")
@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.get_http_client")
def test_submit_clinical_escalation_posts_deep_link_only(mock_get_client, _mock_resolve, mock_settings):
    mock_settings.clinical_risk_alert_from_email = "care-episode-alerts@neosofia.tech"
    mock_settings.frontend_url = "https://staging.neosofia.tech"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    response = MagicMock()
    response.is_success = True
    mock_client.post.return_value = response

    _submit()

    mock_client.post.assert_called_once()
    call = mock_client.post.call_args
    assert call.args[0] == "http://notification:8016/api/emails"
    body = call.kwargs["json"]
    assert body["from_email"] == "care-episode-alerts@neosofia.tech"
    assert body["subject"] == "Clinical risk alert"
    assert "crushing chest pain" not in body["message"]
    assert (
        body["message"]
        == "A patient chat message was flagged as high clinical risk.\n\n"
        "Open the patient record in Neosofia:\n"
        f"https://staging.neosofia.tech/clinician/patients/{PATIENT}?episode_uuid={EPISODE}\n"
    )


@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.get_http_client")
def test_submit_clinical_escalation_upstream_502(mock_get_client, _mock_resolve):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    response = MagicMock()
    response.is_success = False
    response.status_code = 502
    response.reason_phrase = "Bad Gateway"
    response.text = ""
    response.json.side_effect = ValueError("not json")
    mock_client.post.return_value = response

    with pytest.raises(BadGateway, match="temporarily unavailable"):
        _submit()


@patch("src.clients.notification_client.resolve_service_base_url", return_value="http://notification:8016")
@patch("src.clients.notification_client.get_http_client")
def test_submit_clinical_escalation_network_error(mock_get_client, _mock_resolve):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(BadGateway, match="temporarily unavailable"):
        _submit()
