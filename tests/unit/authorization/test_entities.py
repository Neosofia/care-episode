import pytest
from flask import Flask, g, request

from src.authorization import entities
from src.bootstrap.config import settings

pytestmark = pytest.mark.unit
_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def test_principal_tenant_uuid_reads_namespaced_claim():
    app = Flask(__name__)
    app.config["TIER1_ACTOR_CLASSES"] = _DEFAULT_TIER1_ACTORS
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": "00000000-0000-7000-8000-000000002847",
            "neosofia:tenant_uuid": "00000000-0000-7000-8000-000000000099",
        }
        assert entities.principal_tenant_uuid() == "00000000-0000-7000-8000-000000000099"


def test_principal_tenant_uuid_without_request_context():
    assert entities.principal_tenant_uuid() == ""


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


def test_member_entities_bind_path_patient_uuid(app):
    patient_uuid = "00000000-0000-7000-8000-000000000003"
    with app.test_request_context(
        f"/api/v1/care-episodes/{patient_uuid}/records",
        method="GET",
    ):
        request.view_args = {"patient_uuid": patient_uuid}
        g.jwt_claims = {
            "sub": patient_uuid,
            "neosofia:actors": ["patient"],
        }
        principal, resource = entities.care_episode_member_entities()
    assert principal["attrs"]["uuid"] == resource["attrs"]["patientUuid"]
    assert resource["attrs"]["patientUuid"] == patient_uuid
