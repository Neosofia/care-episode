from __future__ import annotations

from typing import Any

import httpx
from flask import abort, request
from platform_client import (
    UpstreamError,
    UpstreamUnavailable,
    outbound_headers,
    raise_for_upstream_response,
)
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.bootstrap.config import settings
from src.clients.mesh_client import resolve_service_base_url, token_broker

CHAT_SERVICE = "chat"
_UNAVAILABLE = "chat service is temporarily unavailable"


def create_interaction(user_uuid: str, *, context: dict | None) -> dict[str, Any]:
    if not context:
        raise BadGateway("chat interaction context is required")
    try:
        base = resolve_service_base_url(CHAT_SERVICE).rstrip("/")
        try:
            access_token = token_broker().get_token(CHAT_SERVICE)
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("authentication service is temporarily unavailable") from exc
        except (RuntimeError, ValueError) as exc:
            raise ServiceUnavailable("failed to obtain service token") from exc

        response = httpx.post(
            f"{base}/api/v1/users/{user_uuid}/interactions",
            headers={
                "Content-Type": "application/json",
                **outbound_headers(access_token=access_token),
            },
            json={"context": context},
            timeout=settings.chat_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway(_UNAVAILABLE) from exc
    except (ServiceUnavailable, BadGateway):
        raise
    except Exception as exc:
        raise BadGateway(_UNAVAILABLE) from exc

    try:
        raise_for_upstream_response(response)
    except UpstreamUnavailable as exc:
        raise BadGateway(_UNAVAILABLE) from exc
    except UpstreamError as exc:
        abort(exc.status_code, description=exc.detail)

    body = response.json()
    if not isinstance(body, dict):
        raise BadGateway(_UNAVAILABLE)
    return body


def create_completion(
    user_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        base = resolve_service_base_url(CHAT_SERVICE).rstrip("/")
        headers = outbound_headers(forward_from=request.headers)
        if "Authorization" not in headers:
            raise BadGateway("chat completion requires caller authorization")

        response = httpx.post(
            f"{base}/api/v1/users/{user_uuid}/interactions/{chat_interaction_uuid}/completions",
            headers={"Content-Type": "application/json", **headers},
            json=payload,
            timeout=settings.chat_service_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise BadGateway(_UNAVAILABLE) from exc
    except (ServiceUnavailable, BadGateway):
        raise
    except Exception as exc:
        raise BadGateway(_UNAVAILABLE) from exc

    try:
        raise_for_upstream_response(response)
    except UpstreamUnavailable as exc:
        raise BadGateway(_UNAVAILABLE) from exc
    except UpstreamError as exc:
        abort(exc.status_code, description=exc.detail)

    body = response.json()
    if not isinstance(body, dict):
        raise BadGateway(_UNAVAILABLE)
    return body
