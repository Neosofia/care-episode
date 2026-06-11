from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import NotFound, ServiceUnavailable

from src.clients import service_registry_client

pytestmark = pytest.mark.unit


@patch("src.clients.service_registry_client.issue_authentication_service_token", return_value="registry-token")
@patch("src.clients.service_registry_client.httpx.get")
@patch("src.clients.service_registry_client.settings")
def test_resolve_service_base_url_success(mock_settings, mock_get, _mock_token):
    service_registry_client._CACHE.clear()
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.authentication_token_timeout_seconds = 5
    mock_settings.service_registry_cache_ttl_seconds = 60
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {"slug": "chat", "base_url": "http://chat:8001"}
    mock_get.return_value = response

    assert service_registry_client.resolve_service_base_url("chat") == "http://chat:8001"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer registry-token"

    mock_get.reset_mock()
    assert service_registry_client.resolve_service_base_url("chat") == "http://chat:8001"
    mock_get.assert_not_called()


@patch("src.clients.service_registry_client.issue_authentication_service_token", return_value="registry-token")
@patch("src.clients.service_registry_client.httpx.get")
@patch("src.clients.service_registry_client.settings")
def test_resolve_service_base_url_not_found(mock_settings, mock_get, _mock_token):
    service_registry_client._CACHE.clear()
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.authentication_token_timeout_seconds = 5
    mock_settings.service_registry_cache_ttl_seconds = 60
    response = MagicMock()
    response.status_code = 404
    response.is_success = False
    mock_get.return_value = response

    with pytest.raises(NotFound, match="service not found"):
        service_registry_client.resolve_service_base_url("missing")


@patch("src.clients.service_registry_client.issue_authentication_service_token", return_value="registry-token")
@patch("src.clients.service_registry_client.httpx.get")
@patch("src.clients.service_registry_client.settings")
def test_resolve_service_base_url_network_error(mock_settings, mock_get, _mock_token):
    service_registry_client._CACHE.clear()
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.authentication_token_timeout_seconds = 5
    mock_get.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(ServiceUnavailable, match="temporarily unavailable"):
        service_registry_client.resolve_service_base_url("chat")
