from __future__ import annotations

from typing import Any

import httpx
from flask import abort, request
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.bootstrap.config import settings
from src.clients.auth_client import issue_chat_service_token
from src.clients.service_registry_client import resolve_service_base_url

CHAT_SERVICE_SLUG = "chat"


def _passthrough_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    active_actor = request.headers.get("X-Active-Actor", "").strip()
    if active_actor:
        headers["X-Active-Actor"] = active_actor
    return headers


def _chat_base() -> str:
    return resolve_service_base_url(CHAT_SERVICE_SLUG).rstrip("/")


def _raise_for_chat_response(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        body = response.json()
        detail = body.get("error") or body.get("message") or body
    except ValueError:
        detail = response.text or response.reason_phrase
    if response.status_code >= 500:
        raise BadGateway("chat service is temporarily unavailable")
    abort(response.status_code, description=str(detail))


def create_interaction(user_uuid: str, *, context: dict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if context:
        payload["context"] = context
    headers = {"Content-Type": "application/json"}
    if context:
        headers["Authorization"] = f"Bearer {issue_chat_service_token()}"
    else:
        headers.update(_passthrough_headers())
    try:
        response = httpx.post(
            f"{_chat_base()}/api/v1/users/{user_uuid}/interactions",
            headers=headers,
            json=payload,
            timeout=settings.chat_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway("chat service is temporarily unavailable") from exc
    _raise_for_chat_response(response)
    return response.json()


def create_completion(
    user_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{_chat_base()}/api/v1/users/{user_uuid}/interactions/{chat_interaction_uuid}/completions",
            headers=_passthrough_headers(),
            json=payload,
            timeout=settings.chat_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway("chat service is temporarily unavailable") from exc
    _raise_for_chat_response(response)
    return response.json()
