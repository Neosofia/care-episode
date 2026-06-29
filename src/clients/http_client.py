from __future__ import annotations

import httpx

_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    """Process-wide outbound HTTP client for upstream service calls."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client()
    return _client


def close_http_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None
