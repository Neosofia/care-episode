from pathlib import Path

import pytest
from authorization_in_the_middle import CedarEvaluator, FilesystemPolicySetSource
from authorization_in_the_middle.entities import build_catalog_entity, build_entity_payload, entity_uid

from src.authorization import entities

pytestmark = pytest.mark.unit

POLICIES_DIR = Path(__file__).resolve().parents[3] / "policies"
TEMPLATE = "00000000-0000-7000-8000-000000002847"
SELF = "00000000-0000-7000-8000-000000000003"
OTHER = "00000000-0000-7000-8000-000000000001"
TENANT = "00000000-0000-7000-8000-000000000010"
OTHER_TENANT = "00000000-0000-7000-8000-000000000099"
CATALOG = entity_uid(f"{entities.NAMESPACE}::CareEpisodeCatalog", entities.CARE_EPISODE_CATALOG_ID)


@pytest.fixture(scope="module")
def evaluator() -> CedarEvaluator:
    return CedarEvaluator(policy_source=FilesystemPolicySetSource(POLICIES_DIR))


def _user(entity_id: str, **flags: bool) -> dict:
    attrs = {
        "uuid": entity_id,
        "tenantId": TENANT,
        "demoTemplatePatientUuid": TEMPLATE,
        **{f"is{name[0].upper()}{name[1:]}": value for name, value in flags.items()},
    }
    return build_entity_payload(f"{entities.NAMESPACE}::User", entity_id, attrs)


def _episode(patient_uuid: str, *, tenant_uuid: str = TENANT) -> dict:
    return entities.build_care_episode_entity(patient_uuid, tenant_uuid=tenant_uuid)


def _catalog(*, tenant_uuid: str = TENANT) -> dict:
    return build_catalog_entity(
        entities.NAMESPACE,
        "CareEpisodeCatalog",
        entities.CARE_EPISODE_CATALOG_ID,
        {"tenantId": tenant_uuid},
    )


def _authorized(
    evaluator: CedarEvaluator,
    *,
    principal: dict,
    action: str,
    resource: dict,
) -> bool:
    principal_uid = principal["uid"]["__entity"]
    resource_uid = resource["uid"]["__entity"]
    return evaluator.is_authorized(
        entity_uid(principal_uid["type"], principal_uid["id"]),
        action,
        entity_uid(resource_uid["type"], resource_uid["id"]),
        [principal, resource],
    )


def test_demo_may_read_template(evaluator):
    principal = _user(SELF, demo=True)
    assert _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(TEMPLATE),
    )


def test_demo_may_write_self(evaluator):
    principal = _user(SELF, demo=True)
    assert _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:create"',
        resource=_episode(SELF),
    )


def test_demo_forbidden_on_other_patient_read(evaluator):
    principal = _user(SELF, demo=True)
    assert not _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(OTHER),
    )


def test_study_forbidden_on_template_read(evaluator):
    principal = _user(SELF, study=True)
    assert not _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(TEMPLATE),
    )


def test_patient_self_read(evaluator):
    principal = _user(SELF, patient=True)
    assert _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(SELF),
    )


def test_patient_forbidden_on_other_member(evaluator):
    principal = _user(SELF, patient=True)
    assert not _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(OTHER),
    )


def test_clinician_may_read_same_tenant_member(evaluator):
    principal = _user(SELF, clinician=True)
    assert _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(OTHER, tenant_uuid=TENANT),
    )


def test_clinician_forbidden_on_other_tenant_member(evaluator):
    principal = _user(SELF, clinician=True)
    assert not _authorized(
        evaluator,
        principal=principal,
        action='Action::"care-episode:list"',
        resource=_episode(OTHER, tenant_uuid=OTHER_TENANT),
    )


def test_clinician_may_list_same_tenant_catalog(evaluator):
    principal = _user(SELF, clinician=True)
    assert evaluator.is_authorized(
        entity_uid(f"{entities.NAMESPACE}::User", SELF),
        'Action::"care-episode:list"',
        CATALOG,
        [principal, _catalog(tenant_uuid=TENANT)],
    )


def test_clinician_forbidden_on_other_tenant_catalog(evaluator):
    principal = _user(SELF, clinician=True)
    assert not evaluator.is_authorized(
        entity_uid(f"{entities.NAMESPACE}::User", SELF),
        'Action::"care-episode:list"',
        CATALOG,
        [principal, _catalog(tenant_uuid=OTHER_TENANT)],
    )
