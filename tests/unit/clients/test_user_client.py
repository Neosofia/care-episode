from unittest.mock import MagicMock, patch

import httpx
import pytest
from platform_client import UpstreamError, UpstreamUnavailable
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.clients import user_client

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000002847"


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.httpx.get")
def test_get_user_profile_success(mock_get, mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.return_value = "service-jwt"
    response = MagicMock()
    response.json.return_value = {
        "display_code": "DEMO-123",
        "first_name": "Alex",
        "last_name": "Patient",
        "email": "alex@example.com",
    }
    mock_get.return_value = response

    profile = user_client.get_user_profile(PATIENT)

    assert profile == {"display_code": "DEMO-123", "display_name": "Alex Patient"}
    mock_get.assert_called_once()
    call = mock_get.call_args
    assert call.args[0] == f"http://user:8015/api/v1/users/{PATIENT}"
    assert call.kwargs["headers"]["X-Active-Actor"] == "operator"


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.httpx.get")
def test_get_user_profile_falls_back_to_email_and_uuid(mock_get, mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.return_value = "service-jwt"
    response = MagicMock()
    response.json.return_value = {"email": "alex@example.com"}
    mock_get.return_value = response

    profile = user_client.get_user_profile(PATIENT)

    assert profile["display_name"] == "alex@example.com"
    assert profile["display_code"] == "00000000"


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.httpx.get")
def test_get_user_profile_not_found_returns_uuid_fallback(mock_get, mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.return_value = "service-jwt"
    response = MagicMock()
    mock_get.return_value = response

    with patch(
        "src.clients.user_client.raise_for_upstream_response",
        side_effect=UpstreamError(status_code=404, detail="not found"),
    ):
        profile = user_client.get_user_profile(PATIENT)

    assert profile == {
        "display_code": "00000000",
        "display_name": "",
    }


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
def test_get_user_profile_token_failure(mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.side_effect = RuntimeError("broker down")

    with pytest.raises(ServiceUnavailable, match="failed to obtain service token"):
        user_client.get_user_profile(PATIENT)


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.httpx.get")
def test_get_user_profile_upstream_unavailable(mock_get, mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.return_value = "service-jwt"
    response = MagicMock()
    mock_get.return_value = response

    with patch(
        "src.clients.user_client.raise_for_upstream_response",
        side_effect=UpstreamUnavailable("timeout"),
    ):
        with pytest.raises(BadGateway, match="temporarily unavailable"):
            user_client.get_user_profile(PATIENT)


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8015")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.httpx.get")
def test_get_user_profile_network_error(mock_get, mock_broker, _mock_resolve):
    mock_broker.return_value.get_token.return_value = "service-jwt"
    mock_get.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(BadGateway, match="temporarily unavailable"):
        user_client.get_user_profile(PATIENT)


@patch("src.clients.user_client.get_user_profile")
def test_patient_labels(mock_get_profile):
    mock_get_profile.return_value = {
        "display_code": "DEMO-123",
        "display_name": "Alex Patient",
    }

    assert user_client.patient_labels(PATIENT) == ("DEMO-123", "Alex Patient")
