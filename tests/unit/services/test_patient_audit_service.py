import datetime
import uuid
from unittest.mock import MagicMock

import pytest

from src.services.patient_audit_service import (
    InvalidAuditSourceError,
    PatientNotFoundError,
    get_patient_audits,
)

PATIENT_ID = uuid.uuid4()
EPISODE_ID = uuid.uuid7()
INTERACTION_ID = uuid.uuid7()
HISTORY_ID = uuid.uuid7()
TENANT_ID = uuid.uuid4()
UTC = datetime.timezone.utc


def test_get_patient_audits_invalid_source():
    db = MagicMock()
    with pytest.raises(InvalidAuditSourceError):
        get_patient_audits(db, str(PATIENT_ID), "invalid", page=1, page_size=10)


def test_get_patient_audits_patient_missing():
    db = MagicMock()
    episode_query = MagicMock()
    episode_query.filter.return_value = episode_query
    episode_query.limit.return_value = episode_query
    episode_query.first.return_value = None
    db.query.return_value = episode_query

    with pytest.raises(PatientNotFoundError):
        get_patient_audits(db, str(PATIENT_ID), "episode", page=1, page_size=10)


def test_get_patient_audits_episode_source_maps_rows():
    db = MagicMock()
    episode_query = MagicMock()
    episode_query.filter.return_value = episode_query
    episode_query.limit.return_value = episode_query
    episode_query.first.return_value = (EPISODE_ID,)

    changed_at = datetime.datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
    row = {
        "history_uuid": HISTORY_ID,
        "episode_uuid": EPISODE_ID,
        "patient_uuid": PATIENT_ID,
        "surgery": "Knee scope",
        "procedure_date": datetime.date(2026, 6, 1),
        "recovery_id": "recovery-1",
        "risk_level": "high",
        "care_window_days": 30,
        "status": "active",
        "tenant_uuid": TENANT_ID,
        "changed_at": changed_at,
        "changed_by_uuid": uuid.UUID("00000000-0000-7000-8000-000000000000"),
        "changed_by_type": 2,
        "change_type": 2,
    }

    db.query.return_value = episode_query
    db.scalar.return_value = 1
    db.execute.return_value.mappings.return_value.all.return_value = [row]

    items, total = get_patient_audits(db, str(PATIENT_ID), "episode", page=1, page_size=10)

    assert total == 1
    assert len(items) == 1
    assert items[0]["risk_level"] == "high"
    assert items[0]["episode_uuid"] == str(EPISODE_ID)
    assert items[0]["changed_at"] == changed_at.isoformat()


def test_get_patient_audits_risk_source_maps_summary():
    db = MagicMock()
    episode_query = MagicMock()
    episode_query.filter.return_value = episode_query
    episode_query.limit.return_value = episode_query
    episode_query.first.return_value = (EPISODE_ID,)

    changed_at = datetime.datetime(2026, 6, 18, 12, 5, tzinfo=UTC)
    row = {
        "history_uuid": HISTORY_ID,
        "chat_interaction_uuid": INTERACTION_ID,
        "patient_uuid": PATIENT_ID,
        "summary": "Patient reports mild swelling; monitoring advised.",
        "changed_at": changed_at,
        "changed_by_uuid": uuid.UUID("00000000-0000-7000-8000-000000000000"),
        "changed_by_type": 2,
        "change_type": 2,
    }

    db.query.return_value = episode_query
    db.scalar.return_value = 1
    db.execute.return_value.mappings.return_value.all.return_value = [row]

    items, total = get_patient_audits(db, str(PATIENT_ID), "risk", page=1, page_size=10)

    assert total == 1
    assert items[0]["summary"] == "Patient reports mild swelling; monitoring advised."
    assert items[0]["chat_interaction_uuid"] == str(INTERACTION_ID)
