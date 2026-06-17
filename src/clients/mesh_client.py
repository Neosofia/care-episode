from __future__ import annotations

import httpx
from platform_client import (
    RegistryUnavailableError,
    ServiceNotRegisteredError,
    ServiceRegistryClient,
    ServiceTokenBroker,
)
from werkzeug.exceptions import NotFound, ServiceUnavailable

from src.bootstrap.config import settings

CARE_EPISODE_CLIENT_ID = "care-episode"

_broker: ServiceTokenBroker | None = None
_registry: ServiceRegistryClient | None = None


def token_broker() -> ServiceTokenBroker:
    global _broker
    if not settings.authentication_service_base_url.strip():
        raise ServiceUnavailable("authentication service is not configured")
    if not settings.care_episode_client_secret.strip():
        raise ServiceUnavailable("care episode service credentials are not configured")
    if _broker is None:
        _broker = ServiceTokenBroker(
            auth_base_url=settings.authentication_service_base_url.strip(),
            client_id=CARE_EPISODE_CLIENT_ID,
            client_secret=settings.care_episode_client_secret.strip(),
            timeout_seconds=settings.authentication_token_timeout_seconds,
        )
    return _broker


def resolve_service_base_url(slug: str) -> str:
    global _registry
    if _registry is None:
        auth_base = settings.authentication_service_base_url.strip()
        if not auth_base:
            raise ServiceUnavailable("authentication service is not configured")
        _registry = ServiceRegistryClient(
            auth_base_url=auth_base,
            token_broker=token_broker(),
            cache_ttl_seconds=float(settings.service_registry_cache_ttl_seconds),
            timeout_seconds=settings.authentication_token_timeout_seconds,
        )
    try:
        return _registry.resolve_base_url(slug)
    except ServiceNotRegisteredError as exc:
        raise NotFound(f"service not found: {exc.slug}") from exc
    except RegistryUnavailableError as exc:
        raise ServiceUnavailable(str(exc)) from exc
