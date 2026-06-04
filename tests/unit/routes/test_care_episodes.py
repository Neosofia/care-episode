import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
TENANT = "00000000-0000-7000-8000-000000000010"
SUB = "00000000-0000-7000-8000-000000000003"


def _token(rsa_keypair, *, actors: list[str], sub: str = SUB) -> str:
    claims = {
        "sub": sub,
        "aud": "care-episode",
        "exp": 9999999999,
        "iat": 1,
        "neosofia:actors": actors,
        "neosofia:tenant_type": "platform",
    }
    return jwt.encode(claims, rsa_keypair["private"], algorithm="RS256")


def _auth_headers(
    rsa_keypair,
    *,
    actors: list[str] | None = None,
    sub: str = SUB,
) -> dict[str, str]:
    actors = actors or ["patient"]
    return {"Authorization": f"Bearer {_token(rsa_keypair, actors=actors, sub=sub)}"}


def test_get_sessions_requires_auth(client):
    response = client.get("/api/v1/care-episodes/sessions", base_url="https://localhost")
    assert response.status_code == 401


def test_post_invite_requires_fields(client, rsa_keypair):
    response = client.post(
        "/api/v1/care-episodes/invites",
        json={},
        headers=_auth_headers(rsa_keypair),
        base_url="https://localhost",
    )
    assert response.status_code == 400


def test_post_invite_returns_token(client, rsa_keypair):
    response = client.post(
        "/api/v1/care-episodes/invites",
        json={"patient_uuid": PATIENT, "procedure_type": "scope", "care_window_days": 14},
        headers=_auth_headers(rsa_keypair),
        base_url="https://localhost",
    )
    assert response.status_code == 201
    assert response.get_json()["invite_token"].startswith("episode_")


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value={"id": "m1", "read_at": "2026-01-01T00:00:00+00:00"})
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read(mock_session, mock_mark, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    message_id = str(uuid.uuid4())
    response = client.patch(
        f"/api/v1/care-episodes/{PATIENT}/messages/{message_id}/read",
        json={},
        headers=_auth_headers(rsa_keypair),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    mock_mark.assert_called_once_with(mock_session.return_value.__enter__.return_value, PATIENT, message_id, changed_by_uuid=PATIENT)


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value=None)
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read_not_found(mock_session, mock_mark, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{PATIENT}/messages/{uuid.uuid4()}/read",
        json={},
        headers=_auth_headers(rsa_keypair),
        base_url="https://localhost",
    )
    assert response.status_code == 404


def test_post_clone_demo_rejects_unknown_actor(client, rsa_keypair):
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/clone-demo",
        json={"tenant_uuid": TENANT, "display_name": "Demo", "display_code": "D-1"},
        headers={
            **_auth_headers(rsa_keypair, actors=["study"]),
            "X-Active-Actor": "study",
        },
        base_url="https://localhost",
    )
    assert response.status_code == 403


def test_post_clone_demo_patient_must_match_principal(client, rsa_keypair):
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/clone-demo",
        json={"tenant_uuid": TENANT, "display_name": "Demo", "display_code": "D-1"},
        headers={
            **_auth_headers(rsa_keypair, actors=["patient"], sub=SUB),
            "X-Active-Actor": "patient",
        },
        base_url="https://localhost",
    )
    assert response.status_code == 403
