"""Cedar principal and entity builders for SDK REST inference."""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle import extract_jwt_principal_entity
from authorization_in_the_middle.entities import build_entity_payload

NAMESPACE = "care_episode"
CARE_EPISODE_CATALOG_ID = "care-episode-catalog"


def resolve_principal() -> dict[str, Any]:
    return extract_jwt_principal_entity(NAMESPACE, default_type="User")


def build_care_episode_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID, {})
