"""Cedar principal and entity builders for SDK REST inference."""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle import extract_jwt_principal_entity
from authorization_in_the_middle.entities import build_entity_payload
from flask import g, has_request_context
from werkzeug.exceptions import BadRequest

NAMESPACE = "care_episode"
CARE_EPISODE_CATALOG_ID = "care-episode-catalog"


def resolve_principal() -> dict[str, Any]:
    return extract_jwt_principal_entity(NAMESPACE, default_type="User")


def principal_tenant_uuid() -> str:
    """Tenant UUID from the authenticated principal JWT (``neosofia:tenant_uuid``)."""
    if not has_request_context() or not getattr(g, "jwt_claims", None):
        return ""
    try:
        entity = extract_jwt_principal_entity(NAMESPACE, default_type="User")
    except BadRequest:
        return ""
    return str(entity.get("attrs", {}).get("tenantId") or "").strip()


def build_care_episode_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID, {})
