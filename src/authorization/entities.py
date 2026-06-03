"""
Cedar principal for REST-inferred ``@with_security`` routes.

Document resources are built from ``src.models.document``; only the principal
is service-specific. JWT → principal mapping uses the SDK helper (including
``neosofia:principal_type`` for demo Patient/Clinician tokens and
``neosofia:actors`` for Tier-1 platform operators; ``neosofia:roles`` for Tier-2 org roles).
"""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle import extract_jwt_principal_entity

NAMESPACE = "care_episode"


def resolve_principal() -> dict[str, Any]:
    return extract_jwt_principal_entity(NAMESPACE, default_type="User")
