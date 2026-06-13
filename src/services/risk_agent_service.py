from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
from werkzeug.exceptions import ServiceUnavailable

from src.bootstrap.config import settings
from src.services.inference_health import risk_inference_configured

INFERENCE_TIMEOUT_SECONDS = 60.0
INFERENCE_MAX_COMPLETION_TOKENS = 512

AGENT_CONTEXT_START = "<<<NEOSOFIA_RISK_CONTEXT_START>>>"
AGENT_CONTEXT_END = "<<<NEOSOFIA_RISK_CONTEXT_END>>>"

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class RiskAgentResult:
    risk_level: str
    summary: str


class RiskAgent:
    """Clinical risk evaluator — prompt is fixed for this service; not user-configurable."""

    SYSTEM_PROMPT = """You are a clinical risk evaluator for post-discharge surgical recovery chat monitoring.

On each patient turn you receive episode context, a rolling thread summary, and the patient's latest message.

Respond with ONLY a single JSON object (no markdown, no prose) using exactly these keys:
- "risk_level": one of "low", "medium", or "high"
- "summary": an updated rolling summary of the conversation thread for the next turn (include clinically relevant facts from the prior summary and this turn; note improvement or worsening; max 400 words; do not copy long verbatim quotes)

Risk level guidance:
- "high": needs immediate clinician attention now (e.g. chest pain, trouble breathing, uncontrolled bleeding, suicidal ideation, signs of sepsis, medication error with harm, fall with head injury, symptoms far outside expected recovery)
- "medium": concerning but not immediate emergency; warrants closer monitoring or clinician follow-up soon
- "low": expected recovery questions or stable/minor issues appropriate for routine AI-assisted support

Rules:
- risk_level may increase OR decrease versus the current level in context
- Use procedure type and days post-op when judging symptom severity
- The summary is the memory for the next turn; keep it concise and clinically useful
"""

    @classmethod
    def format_context_block(cls, context: dict[str, str | int]) -> str:
        lines: list[str] = []
        for key in sorted(context):
            value = context[key]
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            lines.append(f"{key}: {text}")
        if not lines:
            return ""
        body = "\n".join(lines)
        return f"{AGENT_CONTEXT_START}\n{body}\n{AGENT_CONTEXT_END}"

    @classmethod
    def build_user_prompt(
        cls,
        *,
        episode_context: dict[str, str | int],
        prior_summary: str,
        patient_message: str,
    ) -> str:
        context_block = cls.format_context_block(episode_context)
        summary = prior_summary.strip() or "(empty — new interaction)"
        message = patient_message.strip()
        parts = [
            "Evaluate clinical risk for this patient turn.",
            "",
            "Episode context:",
            context_block or "(none)",
            "",
            "Prior thread summary:",
            summary,
            "",
            "Patient's latest message:",
            message,
        ]
        return "\n".join(parts)

    @classmethod
    def _parse_model_payload(cls, raw: str) -> RiskAgentResult:
        text = _JSON_FENCE_RE.sub("", raw.strip()).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("risk agent response must be a JSON object")
        level = str(data.get("risk_level", "")).strip().lower()
        summary = str(data.get("summary", "")).strip()
        if level not in {"low", "medium", "high"}:
            raise ValueError("risk_level must be low, medium, or high")
        if not summary:
            raise ValueError("summary must be non-empty")
        return RiskAgentResult(risk_level=level, summary=summary)

    @classmethod
    def _invoke_model(cls, user_prompt: str) -> str:
        if not risk_inference_configured():
            raise ServiceUnavailable("risk inference is not configured")

        payload = {
            "model": settings.inference_model,
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.inference_temperature,
            "max_completion_tokens": INFERENCE_MAX_COMPLETION_TOKENS,
        }

        try:
            response = httpx.post(
                settings.inference_completions_url,
                headers={
                    "Authorization": f"Bearer {settings.inference_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=INFERENCE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("risk inference is temporarily unavailable") from exc

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceUnavailable("risk inference returned an invalid response") from exc

        reply = str(content).strip()
        if not reply:
            raise ServiceUnavailable("risk inference returned an empty response")
        return reply

    @classmethod
    def evaluate(
        cls,
        *,
        episode_context: dict[str, str | int],
        prior_summary: str,
        patient_message: str,
    ) -> RiskAgentResult:
        user_prompt = cls.build_user_prompt(
            episode_context=episode_context,
            prior_summary=prior_summary,
            patient_message=patient_message,
        )
        last_error: Exception | None = None
        for attempt in range(2):
            raw = cls._invoke_model(
                user_prompt if attempt == 0 else f"{user_prompt}\n\nReturn valid JSON only.",
            )
            try:
                return cls._parse_model_payload(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ServiceUnavailable("risk inference returned an unparseable response") from last_error
