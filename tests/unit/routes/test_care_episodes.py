import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest

pytestmark = pytest.mark.unit

PATIENT = "00000000-0000-7000-8000-000000000001"
TENANT = "00000000-0000-7000-8000-000000000010"
SUB = "00000000-0000-7000-8000-000000000003"


def _token(rsa_keypair, *, actors: list[str], sub: str = SUB, tenant_uuid: str = TENANT) -> str:
    claims = {
        "sub": sub,
        "aud": "care-episode",
        "exp": 9999999999,
        "iat": 1,
        "neosofia:token_type": "human",
        "neosofia:actors": actors,
        "neosofia:tenant_type": "platform",
        "neosofia:tenant_uuid": tenant_uuid,
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


def test_get_care_episodes_requires_auth(client):
    response = client.get("/api/v1/care-episodes", base_url="https://localhost")
    assert response.status_code == 401


def test_get_procedure_catalog_requires_auth(client):
    response = client.get("/api/v1/care-episodes/procedures", base_url="https://localhost")
    assert response.status_code == 401


@patch("src.routes.care_episodes.procedure_catalog_response")
def test_get_procedure_catalog_returns_items(mock_response, client, rsa_keypair):
    mock_response.return_value = {
        "items": [{
            "id": "lap-chole",
            "name": "Laparoscopic cholecystectomy",
            "procedure_type": "general-surgery",
            "emr_ref": "PROC-GS-47562",
            "specialty": "General surgery",
        }],
        "procedure_type_labels": {"general-surgery": "General surgery"},
    }
    response = client.get(
        "/api/v1/care-episodes/procedures?q=chole",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["items"][0]["id"] == "lap-chole"
    assert response.headers["Cache-Control"] == "private, max-age=1800"
    mock_response.assert_called_once_with("chole")


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value={"id": "m1", "read_at": "2026-01-01T00:00:00+00:00"})
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read(mock_session, mock_mark, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    message_id = str(uuid.uuid4())
    response = client.patch(
        f"/api/v1/care-episodes/{SUB}/messages/{message_id}/read",
        json={},
        headers=_auth_headers(rsa_keypair, sub=SUB),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    mock_mark.assert_called_once()
    _, kwargs = mock_mark.call_args
    assert kwargs["changed_by_uuid"] == SUB
    assert kwargs["changed_by_type"] == 1


@patch("src.routes.care_episodes.mark_inbox_message_read", return_value=None)
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_message_read_not_found(mock_session, mock_mark, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{SUB}/messages/{uuid.uuid4()}/read",
        json={},
        headers=_auth_headers(rsa_keypair, sub=SUB),
        base_url="https://localhost",
    )
    assert response.status_code == 404


def _recovery_payload(*, patient_uuid: str = SUB) -> dict:
    return {
        "patient_uuid": patient_uuid,
        "tenant_uuid": TENANT,
        "surgery": "Knee arthroscopy",
        "procedure_date": "2026-01-15",
        "recovery_id": "recovery-demo-001",
        "risk_level": "low",
    }


@patch("src.routes.care_episodes.upsert_episode", return_value={"patient_uuid": SUB})
@patch("src.routes.care_episodes.SessionLocal")
def test_post_care_episode_allows_demo_self(mock_session, mock_upsert, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    response = client.post(
        "/api/v1/care-episodes",
        json=_recovery_payload(patient_uuid=SUB),
        headers={
            **_auth_headers(rsa_keypair, actors=["demo"], sub=SUB),
            "X-Active-Actor": "demo",
        },
        base_url="https://localhost",
    )
    assert response.status_code == 201
    mock_upsert.assert_called_once()


@patch("src.routes.care_episodes.upsert_episode")
@patch("src.routes.care_episodes.SessionLocal")
def test_post_care_episode_forbidden_for_demo_other_patient(mock_session, mock_upsert, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    response = client.post(
        "/api/v1/care-episodes",
        json=_recovery_payload(patient_uuid=PATIENT),
        headers={
            **_auth_headers(rsa_keypair, actors=["demo"], sub=SUB),
            "X-Active-Actor": "demo",
        },
        base_url="https://localhost",
    )
    assert response.status_code == 403
    mock_upsert.assert_not_called()


EPISODE = str(uuid.uuid7())


def _mock_episode_row():
    row = MagicMock()
    row.patient_uuid = uuid.UUID(PATIENT)
    row.episode_uuid = uuid.UUID(EPISODE)
    row.tenant_uuid = uuid.UUID(TENANT)
    return row


@patch("src.services.care_episode_service.get_current_episode", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
@patch("src.routes.care_episodes.list_patient_episodes", return_value=[{"episode_uuid": str(uuid.uuid7()), "is_current": True}])
@patch("src.routes.care_episodes.SessionLocal")
def test_get_patient_episodes(mock_route_session, mock_history, mock_service_session, mock_current, client, rsa_keypair):
    mock_route_session.return_value.__enter__.return_value = MagicMock()
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.get(
        f"/api/v1/care-episodes/{PATIENT}/episodes",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["items"][0]["is_current"] is True
    mock_history.assert_called_once()


@patch("src.services.care_episode_service.get_episode_row", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
@patch("src.routes.care_episodes.get_episode", return_value={"episode_uuid": EPISODE, "is_current": True})
@patch("src.routes.care_episodes.SessionLocal")
def test_get_episode_by_uuid(mock_route_session, mock_get, mock_service_session, mock_get_episode_row, client, rsa_keypair):
    mock_route_session.return_value.__enter__.return_value = MagicMock()
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.get(
        f"/api/v1/care-episodes/{EPISODE}",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["episode_uuid"] == EPISODE
    assert mock_get_episode_row.call_count == 2
    mock_get.assert_called_once()


@patch("src.services.care_episode_service.get_episode_row", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
@patch("src.routes.care_episodes.get_episode", return_value=None)
@patch("src.routes.care_episodes.SessionLocal")
def test_get_episode_by_uuid_not_found(mock_route_session, mock_get, mock_service_session, mock_get_episode_row, client, rsa_keypair):
    mock_route_session.return_value.__enter__.return_value = MagicMock()
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.get(
        f"/api/v1/care-episodes/{EPISODE}",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 404
    assert mock_get_episode_row.call_count == 2
    mock_get.assert_called_once()


@patch("src.services.care_episode_service.get_episode_row", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
@patch("src.routes.care_episodes.patch_episode", return_value={"episode_uuid": EPISODE, "status": "closed"})
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_episode_close(mock_route_session, mock_patch, mock_service_session, mock_get_episode_row, client, rsa_keypair):
    mock_route_session.return_value.__enter__.return_value = MagicMock()
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{EPISODE}",
        json={"status": "closed"},
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "closed"
    assert mock_get_episode_row.call_count == 2
    mock_patch.assert_called_once()


@patch("src.services.care_episode_service.get_episode_row", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
@patch("src.routes.care_episodes.patch_episode", return_value={"episode_uuid": EPISODE, "status": "active"})
@patch("src.routes.care_episodes.SessionLocal")
def test_patch_episode_reopen(mock_route_session, mock_patch, mock_service_session, mock_get_episode_row, client, rsa_keypair):
    mock_route_session.return_value.__enter__.return_value = MagicMock()
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{EPISODE}",
        json={"status": "active"},
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "active"
    assert mock_get_episode_row.call_count == 2
    mock_patch.assert_called_once()


@patch("src.services.care_episode_service.get_episode_row", return_value=_mock_episode_row())
@patch("src.services.care_episode_service.SessionLocal")
def test_patch_episode_rejects_forged_audit_attribution(
    mock_service_session,
    mock_get_episode_row,
    client,
    rsa_keypair,
):
    mock_service_session.return_value.__enter__.return_value = MagicMock()
    response = client.patch(
        f"/api/v1/care-episodes/{EPISODE}",
        json={"status": "closed", "changed_by_uuid": str(uuid.uuid4())},
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 400
    body = response.get_json(silent=True) or {}
    error_text = str(body)
    assert body.get("error") == "invalid_request" or "audit attribution" in error_text


@patch("src.routes.care_episodes.start_new_episode", return_value={"patient_uuid": PATIENT, "status": "active"})
@patch("src.routes.care_episodes.SessionLocal")
def test_post_start_episode(mock_session, mock_start, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    payload = _recovery_payload(patient_uuid=PATIENT)
    del payload["patient_uuid"]
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/episodes",
        json=payload,
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 201
    mock_start.assert_called_once()


def test_study_actor_forbidden_on_patient_write(client, rsa_keypair):
    response = client.post(
        f"/api/v1/care-episodes/{PATIENT}/appointments",
        json={"items": []},
        headers={
            **_auth_headers(rsa_keypair, actors=["study"]),
            "X-Active-Actor": "study",
        },
        base_url="https://localhost",
    )
    assert response.status_code == 403


@patch("src.services.care_episode_service.get_current_episode", return_value=_mock_episode_row())
@patch("src.routes.care_episodes.get_patient_audits")
@patch("src.routes.care_episodes.SessionLocal")
def test_get_patient_audits_route_returns_items(mock_session, mock_get_audits, mock_current, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_get_audits.return_value = (
        [{
            "history_uuid": str(uuid.uuid4()),
            "chat_interaction_uuid": str(uuid.uuid4()),
            "patient_uuid": PATIENT,
            "summary": "Stable recovery.",
            "changed_at": "2026-06-18T12:00:00+00:00",
            "changed_by_uuid": "00000000-0000-7000-8000-000000000000",
            "changed_by_type": 2,
            "change_type": 2,
        }],
        1,
    )
    response = client.get(
        f"/api/v1/care-episodes/{PATIENT}/audits?source=risk&page=1&page_size=20",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "risk"
    assert body["total"] == 1
    assert len(body["items"]) == 1


@patch("src.services.care_episode_service.get_current_episode", return_value=_mock_episode_row())
def test_get_patient_audits_route_requires_source(mock_current, client, rsa_keypair):
    response = client.get(
        f"/api/v1/care-episodes/{PATIENT}/audits",
        headers=_auth_headers(rsa_keypair, actors=["clinician"]),
        base_url="https://localhost",
    )
    assert response.status_code == 400
