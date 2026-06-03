"""
Cedar principal and catalog resources for ``@with_security`` on care-episode routes.

All current API routes authorize against ``care_episode::CareEpisodeCatalog`` with
``care-episode:read`` or ``care-episode:create``; the default policy permits any
authenticated ``care_episode::User`` principal.
"""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle import extract_jwt_principal_entity
from authorization_in_the_middle.entities import build_entity_payload, entity_uid

NAMESPACE = "care_episode"
CARE_EPISODE_CATALOG_ID = "care-episode-catalog"


def resolve_principal() -> dict[str, Any]:
    return extract_jwt_principal_entity(NAMESPACE, default_type="User")


def build_care_episode_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID, {})


def care_episode_catalog_resource_uid() -> str:
    return entity_uid(f"{NAMESPACE}::CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID)


def care_episode_catalog_entities() -> list[dict[str, Any]]:
    return [resolve_principal(), build_care_episode_catalog_entity()]
