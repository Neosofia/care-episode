import uuid
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
TENANT = "00000000-0000-7000-8000-000000000010"


def test_post_invite_requires_fields(client):
    response = client.post("/api/v1/care-episodes/invites", json={}, base_url="https://localhost")
    assert response.status_code == 400


def test_post_invite_returns_token(client):
    response = client.post(
        "/api/v1/care-episodes/invites",
        json={"patient_uuid": PATIENT, "procedure_type": "scope", "care_window_days": 14},
        base_url="https://localhost",
    )
    assert response.status_code == 201
    assert response.get_json()["invite_token"].startswith("episode_")


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value={"id": "m1", "read_at": "2026-01-01T00:00:00+00:00"})
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read(mock_session, mock_mark, client):
    mock_session.return_value.__enter__.return_value = MagicMock()
    message_id = str(uuid.uuid4())
    response = client.patch(
        f"/api/v1/care-episodes/{PATIENT}/messages/{message_id}/read",
        json={},
        base_url="https://localhost",
    )
    assert response.status_code == 200
    mock_mark.assert_called_once_with(mock_session.return_value.__enter__.return_value, PATIENT, message_id, changed_by_uuid=PATIENT)


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value=None)
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read_not_found(mock_session, mock_mark, client):
    mock_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{PATIENT}/messages/{uuid.uuid4()}/read",
        json={},
        base_url="https://localhost",
    )
    assert response.status_code == 404


def test_post_clone_demo_requires_operator(client):
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/clone-demo",
        json={"tenant_uuid": TENANT, "display_name": "Demo", "display_code": "D-1"},
        headers={"X-Active-Actor": "clinician"},
        base_url="https://localhost",
    )
    assert response.status_code == 403
