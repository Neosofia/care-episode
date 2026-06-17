from __future__ import annotations

from typing import Any

import httpx
from platform_client import (
    UpstreamError,
    UpstreamUnavailable,
    outbound_headers,
    raise_for_upstream_response,
)
from werkzeug.exceptions import BadGateway, ServiceUnavailable

from src.bootstrap.config import settings
from src.clients.mesh_client import resolve_service_base_url, token_broker

USER_SERVICE = "user"
_SERVICE_ACTOR = "operator"
_UNAVAILABLE = "user service is temporarily unavailable"


def _display_name(body: dict[str, Any]) -> str:
    first = str(body.get("first_name") or "").strip()
    last = str(body.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name
    return str(body.get("email") or "").strip()


def _display_code(body: dict[str, Any], patient_uuid: str) -> str:
    code = str(body.get("display_code") or "").strip()
    if code:
        return code
    return patient_uuid.replace("-", "")[:8].upper()


def get_user_profile(patient_uuid: str) -> dict[str, str]:
    """Resolve patient labels from the User registry."""
    try:
        base = resolve_service_base_url(USER_SERVICE).rstrip("/")
        try:
            access_token = token_broker().get_token(USER_SERVICE)
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("authentication service is temporarily unavailable") from exc
        except (RuntimeError, ValueError) as exc:
            raise ServiceUnavailable("failed to obtain service token") from exc

        response = httpx.get(
            f"{base}/api/v1/users/{patient_uuid}",
            headers={
                **outbound_headers(access_token=access_token),
                "X-Active-Actor": _SERVICE_ACTOR,
            },
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
        if exc.status_code == 404:
            return {
                "display_code": patient_uuid.replace("-", "")[:8].upper(),
                "display_name": "",
            }
        raise BadGateway(_UNAVAILABLE) from exc

    body = response.json()
    if not isinstance(body, dict):
        raise BadGateway(_UNAVAILABLE)
    return {
        "display_code": _display_code(body, patient_uuid),
        "display_name": _display_name(body),
    }


def patient_labels(patient_uuid: str) -> tuple[str, str]:
    profile = get_user_profile(patient_uuid)
    return profile["display_code"], profile["display_name"]
