from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.clients import chat_client

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
INTERACTION = "00000000-0000-7000-8000-000000000002"


@pytest.fixture
def flask_request_context(app):
    with app.test_request_context(
        "/",
        headers={
            "Authorization": "Bearer test-token",
            "X-Active-Actor": "patient",
        },
    ):
        yield


@patch("src.clients.chat_client.resolve_service_base_url")
def test_create_interaction_requires_registry_lookup(mock_resolve, flask_request_context):
    mock_resolve.side_effect = ServiceUnavailable("failed to resolve service base url")
    with pytest.raises(ServiceUnavailable, match="failed to resolve"):
        chat_client.create_interaction(PATIENT, context=None)


@patch("src.clients.chat_client.resolve_service_base_url", return_value="http://chat:8001")
@patch("src.clients.chat_client.issue_chat_service_token", return_value="service-token")
@patch("src.clients.chat_client.httpx.post")
@patch("src.clients.chat_client.settings")
def test_create_interaction_success(mock_settings, mock_post, _mock_token, _mock_resolve, flask_request_context):
    mock_settings.chat_service_timeout_seconds = 30
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {"chat_interaction_uuid": INTERACTION}
    mock_post.return_value = response

    result = chat_client.create_interaction(PATIENT, context={"procedure_name": "scope"})

    assert result["chat_interaction_uuid"] == INTERACTION
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer service-token"
    assert "X-Active-Actor" not in call_kwargs["headers"]
    assert call_kwargs["json"] == {"context": {"procedure_name": "scope"}}


@patch("src.clients.chat_client.resolve_service_base_url", return_value="http://chat:8001")
@patch("src.clients.chat_client.httpx.post")
@patch("src.clients.chat_client.settings")
def test_create_interaction_upstream_500(mock_settings, mock_post, _mock_resolve, flask_request_context):
    mock_settings.chat_service_timeout_seconds = 30
    response = MagicMock()
    response.is_success = False
    response.status_code = 503
    response.json.side_effect = ValueError()
    response.text = "unavailable"
    response.reason_phrase = "Service Unavailable"
    mock_post.return_value = response

    with pytest.raises(BadGateway):
        chat_client.create_interaction(PATIENT, context=None)


@patch("src.clients.chat_client.resolve_service_base_url", return_value="http://chat:8001")
@patch("src.clients.chat_client.httpx.post")
@patch("src.clients.chat_client.settings")
def test_create_completion_network_error(mock_settings, mock_post, _mock_resolve, flask_request_context):
    mock_settings.chat_service_timeout_seconds = 30
    mock_post.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(BadGateway):
        chat_client.create_completion(PATIENT, INTERACTION, {"content": "hi"})
