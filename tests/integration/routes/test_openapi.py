import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_openapi_spec_contains_core_paths():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["title"] == "Care Episode Service API"
    assert "/health" in spec["paths"]
    assert "/api/v1/care-episodes" in spec["paths"]
    assert "/api/v1/care-episodes/procedures" in spec["paths"]
    assert "/api/v1/care-episodes/{patient_uuid}/chat/interactions" in spec["paths"]
    assert (
        "/api/v1/care-episodes/{patient_uuid}/chat/interactions/{chat_interaction_uuid}/completions"
        in spec["paths"]
    )
    assert (
        "/api/v1/care-episodes/{patient_uuid}/chat/interactions/{chat_interaction_uuid}/messages"
        not in spec["paths"]
    )
    chat_interactions = spec["paths"]["/api/v1/care-episodes/{patient_uuid}/chat/interactions"]
    assert set(chat_interactions) == {"post"}
    assert "/api/v1/care-episodes/{patient_uuid}/transcript" not in spec["paths"]
    for schema in (
        "ChatInteractionListResponse",
        "ChatInteractionSummary",
        "ChatMessageListResponse",
        "ChatMessageSummary",
    ):
        assert schema not in spec["components"]["schemas"]
    assert spec["info"]["version"] == "0.11.0"


def test_openapi_operation_ids_are_unique():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    operation_ids: list[str] = []
    for path_item in spec["paths"].values():
        for method, operation in path_item.items():
            if method.startswith("x") or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id:
                operation_ids.append(operation_id)

    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_spec_defines_episode_risk_level():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    episode = spec["components"]["schemas"]["CareEpisode"]
    assert "risk_level" in episode["required"]
    assert episode["properties"]["risk_level"]["enum"] == ["high", "medium", "low"]
    assert "featured" not in episode["properties"]


def test_openapi_spec_defines_chat_interaction_create_response():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    create_response = spec["components"]["schemas"]["ChatInteractionCreateResponse"]
    assert "care_episode_uuid" in create_response["required"]
    assert "chat_interaction_uuid" in create_response["required"]


def test_openapi_spec_defines_error_schema():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert error_schema["required"] == ["error"]
    assert "authorization_unavailable" in error_schema["properties"]["error"]["enum"]
