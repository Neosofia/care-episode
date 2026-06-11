from __future__ import annotations

import time

import httpx
from werkzeug.exceptions import NotFound, ServiceUnavailable

from src.bootstrap.config import settings
from src.clients.auth_client import issue_authentication_service_token


def _auth_base() -> str:
    base = settings.authentication_service_base_url.strip()
    if not base:
        raise ServiceUnavailable("authentication service is not configured")
    return base.rstrip("/")

_CACHE: dict[str, tuple[str, float]] = {}


def _cache_ttl_seconds() -> float:
    return float(settings.service_registry_cache_ttl_seconds)


def _read_cached(slug: str) -> str | None:
    entry = _CACHE.get(slug)
    if entry is None:
        return None
    base_url, expires_at = entry
    if time.monotonic() >= expires_at:
        _CACHE.pop(slug, None)
        return None
    return base_url


def _write_cache(slug: str, base_url: str) -> None:
    _CACHE[slug] = (base_url, time.monotonic() + _cache_ttl_seconds())


def resolve_service_base_url(slug: str) -> str:
    normalized_slug = slug.strip()
    if not normalized_slug:
        raise ServiceUnavailable("service slug is required")

    cached = _read_cached(normalized_slug)
    if cached:
        return cached

    token = issue_authentication_service_token()
    try:
        response = httpx.get(
            f"{_auth_base()}/api/services/{normalized_slug}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.authentication_token_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ServiceUnavailable("authentication service is temporarily unavailable") from exc

    if response.status_code == 404:
        raise NotFound(f"service not found: {normalized_slug}")
    if not response.is_success:
        raise ServiceUnavailable("failed to resolve service base url")

    body = response.json()
    base_url = str(body.get("base_url") or "").strip()
    if not base_url:
        raise ServiceUnavailable("service registry returned empty base_url")

    _write_cache(normalized_slug, base_url)
    return base_url
