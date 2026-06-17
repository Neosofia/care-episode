import datetime
import uuid

import pytest

from src.models.care_episode import CareEpisode
from src.services.chat_context import build_interaction_context, days_post_op_for

pytestmark = pytest.mark.unit

PATIENT = uuid.UUID("00000000-0000-7000-8000-000000000001")
PATIENT_PROFILE = "Alex Patient"


def _episode(**overrides) -> CareEpisode:
    today = datetime.date.today()
    defaults = {
        "episode_uuid": uuid.uuid7(),
        "patient_uuid": PATIENT,
        "surgery": "Knee scope",
        "procedure_date": today - datetime.timedelta(days=5),
        "recovery_id": "rec-1",
        "last_activity": "2026-06-01T12:00:00Z",
        "risk_level": "low",
        "tenant_uuid": uuid.UUID("00000000-0000-7000-8000-000000000010"),
        "changed_by_uuid": uuid.UUID("00000000-0000-7000-8000-000000000000"),
        "changed_by_type": 2,
    }
    defaults.update(overrides)
    return CareEpisode(**defaults)


def test_build_interaction_context_from_episode():
    episode = _episode()
    context = build_interaction_context(episode, patient_display_name=PATIENT_PROFILE)
    assert context["patient_display_name"] == "Alex Patient"
    assert context["patient_first_name"] == "Alex"
    assert context["procedure_name"] == "Knee scope"
    assert context["procedure_date"] == episode.procedure_date.isoformat()
    assert context["days_post_op"] == days_post_op_for(episode)
    assert context["risk_level"] == "low"
    assert context["tenant_uuid"] == str(episode.tenant_uuid)


def test_build_interaction_context_prefers_jwt_tenant():
    episode = _episode()
    jwt_tenant = "00000000-0000-7000-8000-000000000099"
    context = build_interaction_context(
        episode,
        tenant_uuid=jwt_tenant,
        patient_display_name=PATIENT_PROFILE,
    )
    assert context["tenant_uuid"] == jwt_tenant


def test_build_interaction_context_omits_invalid_risk():
    episode = _episode(risk_level="unknown")
    context = build_interaction_context(episode, patient_display_name=PATIENT_PROFILE)
    assert "risk_level" not in context
