import datetime
import uuid
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jwt
import pytest

from src.models.care_episode import CareEpisode

pytestmark = [pytest.mark.integration, pytest.mark.slow]

TENANT = "00000000-0000-7000-8000-000000000010"
PATIENT = "00000000-0000-7000-8000-000000000001"
SUB = "00000000-0000-7000-8000-000000000003"
EPISODE = "00000000-0000-7000-8000-000000000099"
ACTOR = "00000000-0000-7000-8000-000000000000"
UTC = ZoneInfo("UTC")


def _token(rsa_keypair, *, actors: list[str], sub: str = SUB) -> str:
    claims = {
        "sub": sub,
        "aud": "care-episode",
        "exp": 9999999999,
        "iat": 1,
        "neosofia:token_type": "human",
        "neosofia:actors": actors,
        "neosofia:tenant_type": "platform",
        "neosofia:tenant_uuid": TENANT,
    }
    return jwt.encode(claims, rsa_keypair["private"], algorithm="RS256")


def _auth_headers(rsa_keypair, *, actors: list[str] | None = None) -> dict[str, str]:
    actors = actors or ["clinician"]
    return {"Authorization": f"Bearer {_token(rsa_keypair, actors=actors)}"}


def _seed_active_episode(db) -> None:
    now = datetime.datetime.now(tz=UTC)
    db.add(
        CareEpisode(
            episode_uuid=uuid.UUID(EPISODE),
            patient_uuid=uuid.UUID(PATIENT),
            tenant_uuid=uuid.UUID(TENANT),
            surgery="Knee arthroscopy",
            procedure_date=datetime.date(2026, 1, 15),
            recovery_id="recovery-demo-001",
            last_activity=now.isoformat().replace("+00:00", "Z"),
            risk_level="high",
            care_window_days=30,
            status="active",
            changed_by_uuid=uuid.UUID(ACTOR),
            changed_by_type=2,
        )
    )
    db.commit()


@patch("src.routes.care_episodes.user_client.get_patient_profiles_for_tenant")
@patch("src.routes.care_episodes.SessionLocal")
def test_roster_summary_happy_path(
    mock_session_local,
    mock_profiles,
    client,
    rsa_keypair,
    api_spec,
    validate_response,
    roster_postgres_session_factory,
):
    mock_session_local.side_effect = roster_postgres_session_factory

    with roster_postgres_session_factory() as db:
        _seed_active_episode(db)

    mock_profiles.return_value = {
        PATIENT: {
            "display_code": "DEMO-123",
            "first_name": "Demo",
            "last_name": "Patient",
            "email": "demo@example.com",
        }
    }

    endpoint = "/api/v1/care-episodes/roster-summary"
    response = client.get(
        f"{endpoint}?tenant_uuid={TENANT}&page=1&page_size=4",
        headers=_auth_headers(rsa_keypair),
        base_url="https://localhost",
    )

    assert response.status_code == 200
    body = response.get_json()
    validate_response(api_spec, endpoint, "get", 200, body)
    assert body["high_risk_count"] == 1
    assert body["preview"]["total"] == 1
    assert body["preview"]["items"][0]["patient_uuid"] == PATIENT
    assert body["preview"]["items"][0]["patient"]["display_code"] == "DEMO-123"
    assert body["active_chats"]["items"][0]["patient_uuid"] == PATIENT
    mock_profiles.assert_called_once()
