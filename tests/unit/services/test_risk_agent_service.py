import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from werkzeug.exceptions import ServiceUnavailable

from src.services.risk_agent_service import RiskAgent

pytestmark = pytest.mark.unit


def test_build_user_prompt_includes_context_summary_and_message():
    prompt = RiskAgent.build_user_prompt(
        episode_context={"procedure_name": "Appendectomy", "days_post_op": 3},
        prior_summary="Patient reported mild pain yesterday.",
        patient_message="Pain is much worse and I feel feverish.",
    )
    assert "procedure_name: Appendectomy" in prompt
    assert "Patient reported mild pain yesterday." in prompt
    assert "Pain is much worse" in prompt


def test_parse_model_payload_accepts_fenced_json():
    raw = """```json
{"risk_level": "high", "summary": "Worsening pain and fever on day 3 post-op."}
```"""
    result = RiskAgent._parse_model_payload(raw)
    assert result.risk_level == "high"
    assert "Worsening pain" in result.summary


def test_parse_model_payload_rejects_invalid_level():
    with pytest.raises(ValueError, match="risk_level"):
        RiskAgent._parse_model_payload(json.dumps({"risk_level": "critical", "summary": "x"}))


@patch("src.services.risk_agent_service.httpx.post")
def test_evaluate_returns_parsed_result(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "risk_level": "medium",
                            "summary": "Patient reports increased swelling; monitoring warranted.",
                        },
                    ),
                },
            },
        ],
    }
    mock_post.return_value = mock_response

    with patch("src.services.risk_agent_service.risk_inference_configured", return_value=True):
        result = RiskAgent.evaluate(
            episode_context={"current_risk_level": "low"},
            prior_summary="",
            patient_message="My ankle is more swollen today.",
        )

    assert result.risk_level == "medium"
    assert "swelling" in result.summary


@patch("src.services.risk_agent_service.httpx.post", side_effect=httpx.HTTPError("down"))
def test_evaluate_maps_http_errors(mock_post):
    with (
        patch("src.services.risk_agent_service.risk_inference_configured", return_value=True),
        pytest.raises(ServiceUnavailable, match="temporarily unavailable"),
    ):
        RiskAgent.evaluate(
            episode_context={},
            prior_summary="",
            patient_message="help",
        )
