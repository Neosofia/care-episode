import datetime
import uuid

import pytest

from src.models.care_episode import CareEpisodeSession
from src.services.chat_context import build_interaction_context, days_post_op_for

pytestmark = pytest.mark.unit

PATIENT = uuid.UUID("00000000-0000-7000-8000-000000000001")


def _session(**overrides) -> CareEpisodeSession:
    today = datetime.date.today()
    defaults = {
        "patient_uuid": PATIENT,
        "display_code": "PT-001",
        "display_name": "Alex Patient",
        "surgery": "Knee scope",
        "procedure_date": today - datetime.timedelta(days=5),
        "session_id": "sess-1",
        "risk_level": "low",
        "tenant_uuid": uuid.UUID("00000000-0000-7000-8000-000000000010"),
        "changed_by_uuid": uuid.UUID("00000000-0000-7000-8000-000000000000"),
        "changed_by_type": 2,
    }
    defaults.update(overrides)
    return CareEpisodeSession(**defaults)


def test_build_interaction_context_from_session():
    session = _session()
    context = build_interaction_context(session)
    assert context["patient_display_name"] == "Alex Patient"
    assert context["patient_first_name"] == "Alex"
    assert context["procedure_name"] == "Knee scope"
    assert context["procedure_date"] == session.procedure_date.isoformat()
    assert context["days_post_op"] == days_post_op_for(session)
    assert context["risk_level"] == "low"
    assert context["tenant_uuid"] == str(session.tenant_uuid)


def test_build_interaction_context_prefers_jwt_tenant():
    session = _session()
    jwt_tenant = "00000000-0000-7000-8000-000000000099"
    context = build_interaction_context(session, tenant_uuid=jwt_tenant)
    assert context["tenant_uuid"] == jwt_tenant


def test_build_interaction_context_omits_invalid_risk():
    session = _session(risk_level="unknown")
    context = build_interaction_context(session)
    assert "risk_level" not in context
