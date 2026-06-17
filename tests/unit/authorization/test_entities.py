import pytest
from authorization_in_the_middle.rest_entities import _entities_for_action
from authorization_in_the_middle.service_conventions import _import_entities_module
from flask import Flask, g, request

from src.authorization import entities
from src.bootstrap.config import settings

pytestmark = pytest.mark.unit
_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def test_resolve_principal_sets_demo_template_and_flags(app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": "00000000-0000-7000-8000-000000000003",
            "neosofia:actors": ["demo", "patient"],
        }
        entity = entities.resolve_principal()
    assert entity["attrs"]["demoTemplatePatientUuid"] == settings.demo_template_patient_uuid
    assert entity["attrs"]["isDemo"] is True
    assert entity["attrs"]["isPatient"] is True


def test_registry_care_episode_cedar_attrs_maps_patient_uuid():
    attrs = entities.registry_care_episode_cedar_attrs({"patient_uuid": "00000000-0000-7000-8000-000000000003"})
    assert attrs == {
        "patientUuid": "00000000-0000-7000-8000-000000000003",
    }


def test_registry_care_episode_cedar_attrs_maps_tenant_uuid():
    attrs = entities.registry_care_episode_cedar_attrs(
        {
            "patient_uuid": "00000000-0000-7000-8000-000000000003",
            "tenant_uuid": "00000000-0000-7000-8000-000000000010",
        }
    )
    assert attrs == {
        "patientUuid": "00000000-0000-7000-8000-000000000003",
        "tenantId": "00000000-0000-7000-8000-000000000010",
    }


def test_synthesized_member_entities_bind_path_patient_uuid(app):
    patient_uuid = "00000000-0000-7000-8000-000000000003"
    entities_mod = _import_entities_module()
    with app.test_request_context(
        f"/api/v1/care-episodes/{patient_uuid}/records",
        method="GET",
    ):
        request.view_args = {"patient_uuid": patient_uuid}
        g.jwt_claims = {
            "sub": patient_uuid,
            "neosofia:actors": ["patient"],
        }
        principal, resource = _entities_for_action(
            model_name="care_episode",
            verb="list",
            builder_module_name="care_episode",
            id_arg="patient_uuid",
            resource_type=None,
            entities_mod=entities_mod,
            resource_loader=None,
            namespace=entities.NAMESPACE,
        )
    assert principal["attrs"]["uuid"] == resource["attrs"]["patientUuid"]
    assert resource["attrs"]["patientUuid"] == patient_uuid
