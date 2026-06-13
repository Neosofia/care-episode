"""Cedar entity wiring for the care-episode service."""
from __future__ import annotations

from typing import Any

from authentication_in_the_middle.actors import ensure_tier1_actor_classes
from authorization_in_the_middle.cedar_attrs import tier1_actor_flags
from authorization_in_the_middle.entities import (
    build_catalog_entity,
    build_entity_payload,
    catalog_entities,
    catalog_resource_uid,
    entity_uid,
)
from authorization_in_the_middle.flask_identity import jwt_claim_principal_attributes
from flask import current_app, g, has_app_context, has_request_context, request
from werkzeug.exceptions import BadRequest

from src.bootstrap.config import settings

NAMESPACE = "care_episode"
CARE_EPISODE_CATALOG_ID = "care-episode-catalog"
_USER = f"{NAMESPACE}::User"
_EPISODE = f"{NAMESPACE}::CareEpisode"
_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def _tier1_actors() -> frozenset[str]:
    if has_app_context():
        return ensure_tier1_actor_classes(current_app)
    return _DEFAULT_TIER1_ACTORS


def resolve_principal() -> dict[str, Any]:
    claims = getattr(g, "jwt_claims", None)
    if not claims:
        raise BadRequest("No JWT claims available on request context")
    _, _, jwt_attrs = jwt_claim_principal_attributes(claims)
    actors = jwt_attrs.get("actors")
    jwt_actors = actors if isinstance(actors, list) else []
    entity_id = str(jwt_attrs.get("uuid") or claims.get("sub", ""))
    attrs = {
        "uuid": entity_id,
        "demoTemplatePatientUuid": str(settings.demo_template_patient_uuid).strip(),
        **tier1_actor_flags(jwt_actors, _tier1_actors()),
    }
    return build_entity_payload(_USER, entity_id, attrs)


def _patient_uuid(*, from_body: bool = False) -> str:
    if from_body:
        payload = request.get_json(silent=True) or {}
        return str(payload.get("patient_uuid") or "").strip()
    return str((request.view_args or {}).get("patient_uuid") or "").strip()


def _episode_entity(patient_uuid: str) -> dict[str, Any]:
    patient_uuid = str(patient_uuid).strip()
    return build_entity_payload(_EPISODE, patient_uuid, {"patientUuid": patient_uuid})


def _auth_pair(*, from_body: bool = False) -> list[dict[str, Any]]:
    return [resolve_principal(), _episode_entity(_patient_uuid(from_body=from_body))]


def care_episode_member_resource_uid() -> str:
    return entity_uid(_EPISODE, _patient_uuid())


def care_episode_member_entities() -> list[dict[str, Any]]:
    return _auth_pair()


def recovery_create_resource_uid() -> str:
    return entity_uid(_EPISODE, _patient_uuid(from_body=True))


def recovery_create_entities() -> list[dict[str, Any]]:
    return _auth_pair(from_body=True)


def care_episode_catalog_resource_uid() -> str:
    return catalog_resource_uid(NAMESPACE, "CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID)


def care_episode_catalog_entities() -> list[dict[str, Any]]:
    return catalog_entities(
        resolve_principal,
        lambda: build_catalog_entity(NAMESPACE, "CareEpisodeCatalog", CARE_EPISODE_CATALOG_ID),
    )


def principal_tenant_uuid() -> str:
    if not has_request_context():
        return ""
    claims = getattr(g, "jwt_claims", None)
    if not claims:
        return ""
    _, _, attrs = jwt_claim_principal_attributes(claims)
    return str(attrs.get("tenantId") or "").strip()
