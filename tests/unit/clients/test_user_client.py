from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.clients import user_client

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000010"
PATIENT = "00000000-0000-7000-8000-000000000001"
OTHER_PATIENT = "00000000-0000-7000-8000-000000000002"


@patch("src.clients.user_client.resolve_service_base_url")
def test_list_tenant_patient_users_requires_registry_lookup(mock_resolve):
    mock_resolve.side_effect = ServiceUnavailable("failed to resolve service base url")
    with pytest.raises(ServiceUnavailable, match="failed to resolve"):
        user_client.list_tenant_patient_users(TENANT)
    mock_resolve.assert_called_once()


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8012")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.get_http_client")
def test_list_tenant_patient_users_filters_patient_role(mock_get_client, mock_token_broker, _mock_resolve):
    mock_token_broker.return_value.get_token.return_value = "service-token"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {
        "items": [
            {
                "uuid": PATIENT,
                "tenant_uuid": TENANT,
                "roles": ["patient.self"],
                "display_code": "DEMO-123",
                "first_name": "Demo",
                "last_name": "Patient",
                "email": "demo@example.com",
            },
            {
                "uuid": OTHER_PATIENT,
                "tenant_uuid": TENANT,
                "roles": ["clinician.self"],
                "display_code": "CLN-1",
            },
        ],
        "total": 2,
        "page": 1,
        "page_size": 100,
    }
    mock_client.request.return_value = response

    users = user_client.list_tenant_patient_users(TENANT, search="demo")

    assert len(users) == 1
    assert users[0]["uuid"] == PATIENT
    mock_client.request.assert_called_once()
    call = mock_client.request.call_args
    assert call.args[0] == "GET"
    assert f"/api/v1/tenants/{TENANT}/users" in call.args[1]
    assert call.kwargs["params"]["q"] == "demo"


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8012")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.get_http_client")
def test_get_patient_profiles_for_tenant_filters_requested_uuids(
    mock_get_client,
    mock_token_broker,
    _mock_resolve,
):
    mock_token_broker.return_value.get_token.return_value = "service-token"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {
        "items": [
            {
                "uuid": PATIENT,
                "roles": ["patient.self"],
                "display_code": "DEMO-123",
                "first_name": "Demo",
                "last_name": "Patient",
                "email": "demo@example.com",
            },
            {
                "uuid": OTHER_PATIENT,
                "roles": ["patient.self"],
                "display_code": "DEMO-456",
            },
        ],
        "total": 2,
        "page": 1,
        "page_size": 100,
    }
    mock_client.request.return_value = response

    profiles = user_client.get_patient_profiles_for_tenant(
        TENANT,
        [PATIENT, "00000000-0000-7000-8000-000000000099"],
    )

    assert PATIENT in profiles
    assert profiles[PATIENT]["display_code"] == "DEMO-123"
    assert OTHER_PATIENT not in profiles
    assert "00000000-0000-7000-8000-000000000099" not in profiles
    mock_client.request.assert_called_once()


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8012")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.get_http_client")
def test_get_patient_profiles_for_tenant_raises_when_scan_truncated(
    mock_get_client,
    mock_token_broker,
    _mock_resolve,
):
    mock_token_broker.return_value.get_token.return_value = "service-token"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {
        "items": [],
        "total": 5000,
        "page": 1,
        "page_size": 100,
    }
    mock_client.request.return_value = response

    with pytest.raises(BadGateway, match="registry scan exceeded"):
        user_client.get_patient_profiles_for_tenant(TENANT, [PATIENT])


@patch("src.clients.user_client.resolve_service_base_url", return_value="http://user:8012")
@patch("src.clients.user_client.token_broker")
@patch("src.clients.user_client.get_http_client")
def test_get_patient_profiles_for_tenant_network_error(mock_get_client, mock_token_broker, _mock_resolve):
    mock_token_broker.return_value.get_token.return_value = "service-token"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.request.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(BadGateway, match="user service is temporarily unavailable"):
        user_client.get_patient_profiles_for_tenant(TENANT, [PATIENT])
