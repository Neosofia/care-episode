import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest

pytestmark = pytest.mark.unit

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


@patch("src.routes.care_episodes.create_chat_interaction")
@patch("src.routes.care_episodes.SessionLocal")
def test_post_chat_interaction(mock_session, mock_create_interaction, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_create_interaction.return_value = {
        "care_episode_uuid": PATIENT,
        "chat_interaction_uuid": INTERACTION,
        "user_uuid": PATIENT,
    }
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/chat/interactions",
        headers=_auth_headers(rsa_keypair, sub=PATIENT),
        base_url="https://localhost",
    )
    assert response.status_code == 201
    assert response.get_json()["chat_interaction_uuid"] == INTERACTION


@patch("src.routes.care_episodes.proxy_chat_completion")
@patch("src.routes.care_episodes.SessionLocal")
def test_post_chat_completion(mock_session, mock_proxy, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_proxy.return_value = {"message": "Take it easy today."}
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/chat/interactions/{INTERACTION}/completions",
        json={"content": "I have pain"},
        headers=_auth_headers(rsa_keypair, sub=PATIENT),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Take it easy today."
    mock_proxy.assert_called_once()
