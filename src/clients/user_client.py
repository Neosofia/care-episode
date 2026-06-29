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
from src.bootstrap.logging_config import log_event
from src.clients.http_client import get_http_client
from src.clients.mesh_client import resolve_service_base_url, token_broker

USER_SERVICE = "user"
PATIENT_SELF_ROLE = "patient.self"
_UNAVAILABLE = "user service is temporarily unavailable"
_MAX_SEARCH_PAGES = 10
_SEARCH_PAGE_SIZE = 100
_REGISTRY_SCAN_ROW_LIMIT = _MAX_SEARCH_PAGES * _SEARCH_PAGE_SIZE


def _service_token() -> str:
    try:
        return token_broker().get_token(USER_SERVICE)
    except httpx.HTTPError as exc:
        raise ServiceUnavailable("authentication service is temporarily unavailable") from exc
    except (RuntimeError, ValueError) as exc:
        raise ServiceUnavailable("failed to obtain service token") from exc


def _user_base_url() -> str:
    try:
        return resolve_service_base_url(USER_SERVICE).rstrip("/")
    except (ServiceUnavailable, Exception) as exc:
        if isinstance(exc, ServiceUnavailable):
            raise
        raise ServiceUnavailable("failed to resolve user service base url") from exc


def _raise_if_registry_scan_truncated(*, page: int, total_pages: int, context: str) -> None:
    if page <= total_pages and page > _MAX_SEARCH_PAGES:
        log_event(
            "user_registry.scan_truncated",
            context=context,
            page_limit=_MAX_SEARCH_PAGES,
            row_limit=_REGISTRY_SCAN_ROW_LIMIT,
            total_pages=total_pages,
        )
        raise BadGateway(
            f"user registry scan exceeded {_REGISTRY_SCAN_ROW_LIMIT} rows ({context})"
        )


def _request_json(method: str, url: str, *, params: dict | None = None) -> dict[str, Any]:
    try:
        response = get_http_client().request(
            method,
            url,
            headers={
                "Content-Type": "application/json",
                **outbound_headers(access_token=_service_token()),
            },
            params=params,
            timeout=settings.user_service_timeout_seconds,
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
        raise BadGateway(_UNAVAILABLE) from exc

    body = response.json()
    if not isinstance(body, dict):
        raise BadGateway(_UNAVAILABLE)
    return body


def _is_patient_user(user: dict[str, Any]) -> bool:
    roles = user.get("roles") or []
    return PATIENT_SELF_ROLE in roles


def patient_profile_from_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_code": user.get("display_code"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "email": user.get("email"),
    }


def list_tenant_patient_users(
    tenant_uuid: str,
    *,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Return tenant registry rows with patient.self role, optionally filtered by q."""
    base = _user_base_url()
    trimmed = str(search or "").strip()
    users: list[dict[str, Any]] = []
    page = 1
    total_pages = 1
    while page <= total_pages and page <= _MAX_SEARCH_PAGES:
        params: dict[str, Any] = {
            "page": page,
            "page_size": _SEARCH_PAGE_SIZE,
        }
        if trimmed:
            params["q"] = trimmed
        body = _request_json(
            "GET",
            f"{base}/api/v1/tenants/{tenant_uuid}/users",
            params=params,
        )
        items = body.get("items") or []
        if not isinstance(items, list):
            raise BadGateway(_UNAVAILABLE)
        users.extend(row for row in items if isinstance(row, dict) and _is_patient_user(row))
        total = int(body.get("total") or 0)
        total_pages = max(1, (total + _SEARCH_PAGE_SIZE - 1) // _SEARCH_PAGE_SIZE)
        page += 1
    _raise_if_registry_scan_truncated(
        page=page,
        total_pages=total_pages,
        context="tenant patient list",
    )
    return users


def search_tenant_patient_uuids(tenant_uuid: str, search: str) -> list[str]:
    trimmed = str(search or "").strip()
    if not trimmed:
        return []
    return [
        str(user["uuid"])
        for user in list_tenant_patient_users(tenant_uuid, search=trimmed)
        if user.get("uuid")
    ]


def get_patient_profiles_for_tenant(
    tenant_uuid: str,
    user_uuids: list[str],
) -> dict[str, dict[str, Any]]:
    """Resolve patient profile fields with paginated tenant list calls (not per-user GET)."""
    trimmed_tenant = str(tenant_uuid or "").strip()
    needed: set[str] = set()
    for user_uuid in user_uuids:
        normalized = str(user_uuid or "").strip()
        if normalized:
            needed.add(normalized)
    if not trimmed_tenant or not needed:
        return {}

    base = _user_base_url()
    profiles: dict[str, dict[str, Any]] = {}
    page = 1
    total_pages = 1
    while page <= total_pages and page <= _MAX_SEARCH_PAGES:
        if not needed - profiles.keys():
            break
        body = _request_json(
            "GET",
            f"{base}/api/v1/tenants/{trimmed_tenant}/users",
            params={"page": page, "page_size": _SEARCH_PAGE_SIZE},
        )
        items = body.get("items") or []
        if not isinstance(items, list):
            raise BadGateway(_UNAVAILABLE)
        for row in items:
            if not isinstance(row, dict):
                continue
            user_uuid = str(row.get("uuid") or "").strip()
            if user_uuid in needed and _is_patient_user(row):
                profiles[user_uuid] = patient_profile_from_user(row)
        total = int(body.get("total") or 0)
        total_pages = max(1, (total + _SEARCH_PAGE_SIZE - 1) // _SEARCH_PAGE_SIZE)
        page += 1

    missing = needed - profiles.keys()
    if missing:
        _raise_if_registry_scan_truncated(
            page=page,
            total_pages=total_pages,
            context="patient profile lookup",
        )
    return profiles
