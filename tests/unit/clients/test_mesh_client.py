from unittest.mock import MagicMock, patch

import httpx
import pytest
from platform_client import RegistryUnavailableError, ServiceNotRegisteredError
from werkzeug.exceptions import NotFound, ServiceUnavailable

from src.clients import mesh_client

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_mesh_clients():
    mesh_client._broker = None
    mesh_client._registry = None
    yield
    mesh_client._broker = None
    mesh_client._registry = None


@patch("src.clients.mesh_client.settings")
def test_token_broker_requires_auth_base(mock_settings):
    mock_settings.authentication_service_base_url = ""
    mock_settings.care_episode_client_secret = "secret"
    with pytest.raises(ServiceUnavailable, match="authentication service is not configured"):
        mesh_client.token_broker()


@patch("src.clients.mesh_client.settings")
def test_token_broker_requires_client_secret(mock_settings):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = ""
    with pytest.raises(ServiceUnavailable, match="credentials are not configured"):
        mesh_client.token_broker()


@patch("src.clients.mesh_client.settings")
def test_token_broker_success(mock_settings):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.care_episode_client_secret = "secret"
    mock_settings.authentication_token_timeout_seconds = 5
    broker = MagicMock()
    broker.get_token.return_value = "chat-service-jwt"
    mesh_client._broker = broker

    assert mesh_client.token_broker() is broker
    assert broker.get_token("chat") == "chat-service-jwt"


def test_resolve_service_base_url_success():
    registry = MagicMock()
    registry.resolve_base_url.return_value = "http://chat:8001"
    mesh_client._registry = registry

    assert mesh_client.resolve_service_base_url("chat") == "http://chat:8001"
    registry.resolve_base_url.assert_called_once_with("chat")


def test_resolve_service_base_url_not_found():
    registry = MagicMock()
    registry.resolve_base_url.side_effect = ServiceNotRegisteredError("missing")
    mesh_client._registry = registry

    with pytest.raises(NotFound, match="service not found: missing"):
        mesh_client.resolve_service_base_url("missing")


def test_resolve_service_base_url_unavailable():
    registry = MagicMock()
    registry.resolve_base_url.side_effect = RegistryUnavailableError(
        "authentication service is temporarily unavailable"
    )
    mesh_client._registry = registry

    with pytest.raises(ServiceUnavailable, match="temporarily unavailable"):
        mesh_client.resolve_service_base_url("chat")


@patch("src.clients.mesh_client.token_broker")
@patch("src.clients.mesh_client.settings")
def test_resolve_service_base_url_lazy_inits_registry(mock_settings, mock_token_broker):
    mock_settings.authentication_service_base_url = "http://authentication:8014"
    mock_settings.service_registry_cache_ttl_seconds = 60
    mock_settings.authentication_token_timeout_seconds = 5
    mock_broker = MagicMock()
    mock_token_broker.return_value = mock_broker

    with patch("src.clients.mesh_client.ServiceRegistryClient") as mock_registry_cls:
        registry = MagicMock()
        registry.resolve_base_url.return_value = "http://chat:8001"
        mock_registry_cls.return_value = registry

        assert mesh_client.resolve_service_base_url("chat") == "http://chat:8001"
        mock_registry_cls.assert_called_once_with(
            auth_base_url="http://authentication:8014",
            token_broker=mock_broker,
            cache_ttl_seconds=60.0,
            timeout_seconds=5,
        )
