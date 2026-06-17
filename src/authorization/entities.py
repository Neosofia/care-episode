"""Cedar entity wiring for the care-episode service."""
from __future__ import annotations

from typing import Any

from authentication_in_the_middle.actors import ensure_tier1_actor_classes
from authorization_in_the_middle.entities import build_entity_payload
from authorization_in_the_middle.flask_identity import resolve_jwt_principal
from flask import current_app, has_app_context

from src.bootstrap.config import settings

NAMESPACE = "care_episode"
CARE_EPISODE_CATALOG_ID = "care-episode-catalog"
MEMBER_ID_FIELD = "patient_uuid"

_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def tier1_actor_classes() -> frozenset[str]:
    if has_app_context():
        return ensure_tier1_actor_classes(current_app)
    return _DEFAULT_TIER1_ACTORS


def resolve_principal() -> dict[str, Any]:
    return resolve_jwt_principal(
        NAMESPACE,
        actor_classes=tier1_actor_classes(),
        require_claims=True,
        extra_attrs={"demoTemplatePatientUuid": str(settings.demo_template_patient_uuid).strip()},
    )


def registry_care_episode_cedar_attrs(row: dict[str, Any]) -> dict[str, Any]:
    """Map patient rows to Cedar member attrs (SDK synthesizes builders from this)."""
    patient_uuid = str(row.get("patient_uuid") or row.get(MEMBER_ID_FIELD) or "").strip()
    attrs: dict[str, Any] = {"patientUuid": patient_uuid}
    tenant_uuid = str(row.get("tenant_uuid") or "").strip()
    if tenant_uuid:
        attrs["tenantId"] = tenant_uuid
    return attrs


def build_care_episode_entity(patient_uuid: str, *, tenant_uuid: str = "") -> dict[str, Any]:
    """Manual Cedar entity for policy unit tests."""
    patient_uuid = str(patient_uuid).strip()
    row = {"patient_uuid": patient_uuid}
    if tenant_uuid:
        row["tenant_uuid"] = tenant_uuid
    return build_entity_payload(
        f"{NAMESPACE}::CareEpisode",
        patient_uuid,
        registry_care_episode_cedar_attrs(row),
    )
