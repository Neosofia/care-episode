from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import ServiceUnavailable

from src.clients import auth_client

pytestmark = pytest.mark.unit


@patch("src.clients.auth_client.settings")
def test_issue_chat_service_token_requires_auth_base(mock_settings):
    mock_settings.authentication_service_base_url = ""
    mock_settings.care_episode_client_secret = "secret"
    with pytest.raises(ServiceUnavailable, match="authentication service is not configured"):
        auth_client.issue_chat_service_token()


@patch("src.clients.auth_client.settings")
def test_issue_chat_service_token_requires_client_secret(mock_settings):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = ""
    with pytest.raises(ServiceUnavailable, match="credentials are not configured"):
        auth_client.issue_chat_service_token()


@patch("src.clients.auth_client.httpx.post")
@patch("src.clients.auth_client.settings")
def test_issue_chat_service_token_success(mock_settings, mock_post):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = "secret"
    mock_settings.authentication_token_timeout_seconds = 5
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {"access_token": "chat-service-jwt"}
    mock_post.return_value = response

    token = auth_client.issue_chat_service_token()

    assert token == "chat-service-jwt"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["data"]["grant_type"] == "client_credentials"
    assert call_kwargs["data"]["audience"] == "chat"
    assert call_kwargs["headers"]["Authorization"].startswith("Basic ")


@patch("src.clients.auth_client.httpx.post")
@patch("src.clients.auth_client.settings")
def test_issue_chat_service_token_upstream_error(mock_settings, mock_post):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = "secret"
    mock_settings.authentication_token_timeout_seconds = 5
    response = MagicMock()
    response.is_success = False
    mock_post.return_value = response

    with pytest.raises(ServiceUnavailable, match="failed to obtain"):
        auth_client.issue_chat_service_token()


@patch("src.clients.auth_client.httpx.post")
@patch("src.clients.auth_client.settings")
def test_issue_chat_service_token_network_error(mock_settings, mock_post):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = "secret"
    mock_settings.authentication_token_timeout_seconds = 5
    mock_post.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(ServiceUnavailable, match="temporarily unavailable"):
        auth_client.issue_chat_service_token()
