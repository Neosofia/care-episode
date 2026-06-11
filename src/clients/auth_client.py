from __future__ import annotations

import base64

import httpx
from werkzeug.exceptions import ServiceUnavailable

from src.bootstrap.config import settings

CARE_EPISODE_CLIENT_ID = "care-episode"
AUTHENTICATION_AUDIENCE = "authentication"


def _auth_base() -> str:
    base = settings.authentication_service_base_url.strip()
    if not base:
        raise ServiceUnavailable("authentication service is not configured")
    return base.rstrip("/")


def issue_service_token(*, audience: str) -> str:
    secret = settings.care_episode_client_secret.strip()
    if not secret:
        raise ServiceUnavailable("care episode service credentials are not configured")
    credentials = base64.b64encode(f"{CARE_EPISODE_CLIENT_ID}:{secret}".encode()).decode()
    try:
        response = httpx.post(
            f"{_auth_base()}/api/token",
            data={"grant_type": "client_credentials", "audience": audience},
            headers={"Authorization": f"Basic {credentials}"},
            timeout=settings.authentication_token_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ServiceUnavailable("authentication service is temporarily unavailable") from exc
    if not response.is_success:
        raise ServiceUnavailable("failed to obtain service token")
    body = response.json()
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise ServiceUnavailable("failed to obtain service token")
    return token


def issue_authentication_service_token() -> str:
    return issue_service_token(audience=AUTHENTICATION_AUDIENCE)


def issue_chat_service_token() -> str:
    return issue_service_token(audience="chat")
