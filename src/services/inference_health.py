from __future__ import annotations

from src.bootstrap.config import settings


def risk_inference_configured() -> bool:
    return bool(
        settings.inference_api_key
        and settings.inference_completions_url
        and str(settings.inference_model).strip()
    )
