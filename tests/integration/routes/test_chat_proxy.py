import datetime
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest

pytestmark = pytest.mark.integration

PATIENT = "00000000-0000-7000-8000-000000000001"
INTERACTION = "00000000-0000-7000-8000-000000000002"
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


def _auth_headers(rsa_keypair, *, actors: list[str] | None = None, sub: str = SUB) -> dict[str, str]:
    actors = actors or ["patient"]
    return {"Authorization": f"Bearer {_token(rsa_keypair, actors=actors, sub=sub)}"}


def _episode_row():
    from src.models.care_episode import CareEpisode

    return CareEpisode(
        episode_uuid=uuid.UUID("00000000-0000-7000-8000-000000000099"),
        patient_uuid=uuid.UUID(PATIENT),
        surgery="Knee scope",
        procedure_date=datetime.date.today(),
        recovery_id="sess-1",
        last_activity="2026-06-11T12:00:00Z",
        risk_level="low",
        status="active",
        tenant_uuid=uuid.UUID("00000000-0000-7000-8000-000000000010"),
        changed_by_uuid=uuid.UUID("00000000-0000-7000-8000-000000000000"),
        changed_by_type=2,
    )


@patch(
    "src.services.chat_proxy_service.user_client.get_user_profile",
    return_value={"display_code": "PT-001", "display_name": "Alex Patient"},
)
@patch("src.clients.chat_client.create_interaction")
@patch("src.services.chat_proxy_service.get_active_episode")
@patch("src.routes.care_episodes.SessionLocal")
def test_chat_interaction_create_happy_path(
    mock_session,
    mock_active_episode,
    mock_create_interaction,
    _mock_user_profile,
    client,
    rsa_keypair,
    api_spec,
    validate_response,
):
    mock_session.return_value.__enter__.return_value = MagicMock()
    episode = _episode_row()
    mock_active_episode.return_value = episode
    mock_create_interaction.return_value = {
        "chat_interaction_uuid": INTERACTION,
        "user_uuid": PATIENT,
        "started_at": "2026-06-11T12:00:00+00:00",
        "last_message_at": None,
        "message_count": 0,
        "preview": None,
    }

    endpoint = f"/api/v1/care-episodes/{PATIENT}/chat/interactions"
    response = client.post(endpoint, headers=_auth_headers(rsa_keypair, sub=PATIENT), base_url="https://localhost")

    assert response.status_code == 201
    body = response.get_json()
    assert body["chat_interaction_uuid"] == INTERACTION
    assert body["care_episode_uuid"] == str(episode.episode_uuid)
    mock_create_interaction.assert_called_once()
    validate_response(api_spec, endpoint, "post", 201, body)


@patch("src.clients.chat_client.create_interaction")
@patch("src.services.chat_proxy_service.get_active_episode", return_value=None)
@patch("src.routes.care_episodes.SessionLocal")
def test_chat_interaction_create_no_episode_skips_chat_call(mock_session, _mock_active, mock_create_interaction, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()

    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/chat/interactions",
        headers=_auth_headers(rsa_keypair, sub=PATIENT),
        base_url="https://localhost",
    )

    assert response.status_code == 404
    mock_create_interaction.assert_not_called()
