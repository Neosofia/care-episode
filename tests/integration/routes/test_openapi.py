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
    assert "/api/v1/care-episodes/sessions" in spec["paths"]
    assert "/api/v1/care-episodes/{patient_uuid}/clone-demo" in spec["paths"]
    assert "/api/v1/care-episodes/{patient_uuid}/transcript" not in spec["paths"]


def test_openapi_spec_defines_session_risk_level():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    session = spec["components"]["schemas"]["CareEpisodeSession"]
    assert "risk_level" in session["required"]
    assert session["properties"]["risk_level"]["enum"] == ["high", "medium", "low"]
    assert "featured" not in session["properties"]


def test_openapi_spec_defines_error_schema():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert error_schema["required"] == ["error"]
    assert "authorization_unavailable" in error_schema["properties"]["error"]["enum"]
